import axios from 'axios';
import {
  TerraformResource,
  TerraformVariable,
  ApiResponse
} from '../types';

const API_BASE_URL = '/api/terraform';

const TF_EXIT_PREFIX = '__TF_EXIT__:';
const TF_EXIT_REGEX = /^__TF_EXIT__:(\d)(?:\n|$)/m;

function processStreamChunk(
  buffer: { current: string },
  chunk: string,
  onData: (text: string) => void
): number | null {
  buffer.current += chunk;
  const idx = buffer.current.indexOf(TF_EXIT_PREFIX);
  if (idx === -1) {
    const keep = TF_EXIT_PREFIX.length + 2;
    const safe = buffer.current.length <= keep ? 0 : buffer.current.length - keep;
    const toEmit = buffer.current.slice(0, safe);
    if (toEmit) onData(toEmit);
    buffer.current = buffer.current.slice(safe);
    return null;
  }
  const tail = buffer.current.slice(idx);
  const match = tail.match(TF_EXIT_REGEX);
  if (!match) {
    onData(buffer.current.slice(0, idx));
    buffer.current = tail;
    return null;
  }
  onData(buffer.current.slice(0, idx));
  buffer.current = '';
  return match[1] === '0' ? 0 : 1;
}

function flushStreamBuffer(buffer: { current: string }, onData: (text: string) => void): number | null {
  const idx = buffer.current.indexOf(TF_EXIT_PREFIX);
  if (idx === -1) {
    if (buffer.current) onData(buffer.current);
    return null;
  }
  onData(buffer.current.slice(0, idx));
  const match = buffer.current.slice(idx).match(TF_EXIT_REGEX);
  return match ? (match[1] === '0' ? 0 : 1) : null;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
});

export interface OnboardingStatus {
  onboarding_required: boolean;
  reason?: string;
  message: string;
  next_steps?: string[];
}

export interface ConfigOnboardingStep {
  name: string;
  label: string;
  filled: boolean;
  sensitive: boolean;
}

export interface ConfigOnboardingPhase {
  id: number;
  name: string;
  variables: ConfigOnboardingStep[];
  all_filled: boolean;
}

export interface ConfigOnboardingStatus {
  config_onboarding_required: boolean;
  phases: ConfigOnboardingPhase[];
  steps: ConfigOnboardingStep[];
}

export interface AwsVpc {
  id: string;
  cidr: string;
  name: string;
}

export interface AwsSubnet {
  id: string;
  cidr: string;
  az: string;
  name: string;
}

export const terraformApi = {
  getOnboardingStatus: async (): Promise<OnboardingStatus> => {
    const response = await api.get<OnboardingStatus>('/onboarding/status');
    return response.data;
  },

  getConfigOnboardingStatus: async (): Promise<ConfigOnboardingStatus> => {
    const response = await api.get<ConfigOnboardingStatus>('/onboarding/config-status');
    return response.data;
  },

  syncTfvarsToInstances: async (): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>('/onboarding/sync-tfvars-to-instances');
    return response.data;
  },

  syncToParameterStore: async (): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>('/onboarding/sync-to-parameter-store');
    return response.data;
  },

  getAwsVpcs: async (region: string): Promise<{ vpcs: AwsVpc[] }> => {
    const response = await api.get<{ vpcs: AwsVpc[] }>('/aws/vpcs', { params: { region } });
    return response.data;
  },

  getAwsSubnets: async (region: string, vpcId: string): Promise<{ subnets: AwsSubnet[] }> => {
    const response = await api.get<{ subnets: AwsSubnet[] }>('/aws/subnets', { params: { region, vpc_id: vpcId } });
    return response.data;
  },

  createAwsKeyPair: async (): Promise<{ key_name: string; private_key: string; key_path: string; ssh_hint: string }> => {
    const response = await api.post<{ key_name: string; private_key: string; key_path: string; ssh_hint: string }>('/aws/key-pair');
    return response.data;
  },

  getInitStatus: async (resourceId: string): Promise<{ initialized: boolean; resource_id: string }> => {
    const response = await api.get<{ initialized: boolean; resource_id: string }>(`/init/${resourceId}/status`);
    return response.data;
  },

  initResource: async (resourceId: string): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>(`/init/${resourceId}`);
    return response.data;
  },

  streamInitResource: async (
    resourceId: string,
    onData: (chunk: string) => void,
    onComplete: (success: boolean) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const response = await fetch(
      `${API_BASE_URL}/init/stream/${resourceId}`,
      { signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const buffer = { current: '' };
    let exitCode: number | null = null;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const code = processStreamChunk(buffer, chunk, onData);
        if (code !== null) exitCode = code;
      }
      if (exitCode === null) exitCode = flushStreamBuffer(buffer, onData);
      onComplete(exitCode === 0);
    } catch (error) {
      onData(`\nError: ${error}\n`);
      onComplete(false);
    }
  },

  getResources: async (): Promise<TerraformResource[]> => {
    const response = await api.get<TerraformResource[]>('/resources');
    return response.data;
  },

  getVariables: async (): Promise<TerraformVariable[]> => {
    const response = await api.get<TerraformVariable[]>('/variables');
    return response.data;
  },

  getResourceVariables: async (resourceId: string): Promise<TerraformVariable[]> => {
    const response = await api.get<TerraformVariable[]>(`/resources/${resourceId}/variables`);
    return response.data;
  },

  getResourceDescription: async (resourceId: string): Promise<{ content: string }> => {
    const response = await api.get<{ content: string }>(`/resources/${resourceId}/description`);
    return response.data;
  },

  updateRootVariable: async (varName: string, value: string): Promise<ApiResponse> => {
    const response = await api.put<ApiResponse>(`/variables/${varName}`, { value });
    return response.data;
  },

  updateInstanceVariable: async (resourceId: string, varName: string, value: string): Promise<ApiResponse> => {
    const response = await api.put<ApiResponse>(`/resources/${resourceId}/variables/${varName}`, { value });
    return response.data;
  },

  restoreResourceVariables: async (resourceId: string): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>(`/resources/${resourceId}/variables/restore`);
    return response.data;
  },

  output: async (resourceId?: string): Promise<ApiResponse> => {
    const url = resourceId ? `/output?resource_id=${resourceId}` : '/output';
    const response = await api.get<ApiResponse>(url);
    return response.data;
  },

  forceUnlock: async (resourceId: string, lockId: string): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>(`/force-unlock/${resourceId}`, { lock_id: lockId });
    return response.data;
  },

  refreshResourceStatus: async (resourceId: string): Promise<{ resource_id: string; status: string }> => {
    const response = await api.post<{ resource_id: string; status: string }>(`/resources/${resourceId}/refresh-status`);
    return response.data;
  },

  streamApplyResource: async (
    resourceId: string,
    autoApprove: boolean = false,
    onData: (chunk: string) => void,
    onComplete: (success: boolean) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const response = await fetch(
      `${API_BASE_URL}/apply/stream/${resourceId}?auto_approve=${autoApprove}`,
      { signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const buffer = { current: '' };
    let exitCode: number | null = null;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const code = processStreamChunk(buffer, chunk, onData);
        if (code !== null) exitCode = code;
      }
      if (exitCode === null) exitCode = flushStreamBuffer(buffer, onData);
      onComplete(exitCode === 0);
    } catch (error) {
      onData(`\nError: ${error}\n`);
      onComplete(false);
    }
  },

  streamDestroyResource: async (
    resourceId: string,
    autoApprove: boolean = false,
    onData: (chunk: string) => void,
    onComplete: (success: boolean) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const response = await fetch(
      `${API_BASE_URL}/destroy/stream/${resourceId}?auto_approve=${autoApprove}`,
      { signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const buffer = { current: '' };
    let exitCode: number | null = null;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const code = processStreamChunk(buffer, chunk, onData);
        if (code !== null) exitCode = code;
      }
      if (exitCode === null) exitCode = flushStreamBuffer(buffer, onData);
      onComplete(exitCode === 0);
    } catch (error) {
      onData(`\nError: ${error}\n`);
      onComplete(false);
    }
  },

  streamPlanResource: async (
    resourceId: string,
    onData: (chunk: string) => void,
    onComplete: (success: boolean) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const response = await fetch(
      `${API_BASE_URL}/plan/stream/${resourceId}`,
      { signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const buffer = { current: '' };
    let exitCode: number | null = null;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const code = processStreamChunk(buffer, chunk, onData);
        if (code !== null) exitCode = code;
      }
      if (exitCode === null) exitCode = flushStreamBuffer(buffer, onData);
      onComplete(exitCode === 0);
    } catch (error) {
      onData(`\nError: ${error}\n`);
      onComplete(false);
    }
  },
};

// Backend Setup API
export interface BackendSetupRequest {
  bucket_name: string;
  table_name?: string;
  region?: string;
}

export interface BackendSetupResult {
  success: boolean;
  message: string;
  details?: any;
  backend_files_generated?: number;
}

export interface BackendStatus {
  configured: boolean;
  total_instances: number;
  instances_with_backend: number;
  instances: Array<{
    name: string;
    has_backend: boolean;
  }>;
}

export const backendApi = {
  getSuggestedBucketName: async (namePrefix: string): Promise<{ bucket_name: string; table_name: string; bucket_pattern: string; table_pattern: string }> => {
    const response = await axios.post('/api/backend/suggest-bucket-name', { name_prefix: namePrefix });
    return response.data;
  },

  checkNamePrefix: async (prefix: string): Promise<{ available: boolean; error?: string }> => {
    const response = await axios.get(`/api/terraform/check-name-prefix/${encodeURIComponent(prefix)}`);
    return response.data;
  },

  setupBackend: async (request: BackendSetupRequest): Promise<BackendSetupResult> => {
    const response = await axios.post('/api/backend/setup', request);
    return response.data;
  },

  checkBackend: async (request: BackendSetupRequest) => {
    const response = await axios.post('/api/backend/check', request);
    return response.data;
  },

  getStatus: async (): Promise<BackendStatus> => {
    const response = await axios.get('/api/backend/status');
    return response.data;
  },

  rebuildBackendForInstance: async (instanceName: string, request: BackendSetupRequest): Promise<{ success: boolean; instance: string; backend_file: string }> => {
    const response = await axios.post(`/api/backend/generate/${instanceName}`, request);
    return response.data;
  },
};

// Key Management API
export interface KeyUploadRequest {
  key_name: string;
  private_key_content: string;
  description?: string;
}

export interface KeyInfo {
  name: string;
  description?: string;
  last_modified?: string;
  version?: number;
  tier?: string;
}

export const keysApi = {
  listKeys: async () => {
    const response = await axios.get('/api/keys/list');
    return response.data;
  },

  uploadKey: async (request: KeyUploadRequest) => {
    const response = await axios.post('/api/keys/upload', request);
    return response.data;
  },

  uploadKeyFile: async (keyName: string, file: File, description?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(
      `/api/keys/upload-file?key_name=${encodeURIComponent(keyName)}&description=${encodeURIComponent(description || '')}`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' }
      }
    );
    return response.data;
  },

  getKeyInfo: async (keyName: string): Promise<KeyInfo> => {
    const response = await axios.get(`/api/keys/${keyName}`);
    return response.data;
  },

  deleteKey: async (keyName: string) => {
    const response = await axios.delete(`/api/keys/${keyName}`);
    return response.data;
  },

  getStorageInfo: async () => {
    const response = await axios.get('/api/keys/storage/info');
    return response.data;
  },
};

export interface DangerZoneStatus {
  enabled_count: number;
  enabled_resources: string[];
  hard_reset_available: boolean;
}

export interface HardResetResult {
  success: boolean;
  message: string;
  details: Record<string, { success: boolean; actions: string[]; error?: string }>;
}

export const dangerZoneApi = {
  getStatus: async (): Promise<DangerZoneStatus> => {
    const response = await axios.get<DangerZoneStatus>('/api/danger-zone/status');
    return response.data;
  },

  streamDestroyAll: async (
    onData: (chunk: string) => void,
    onComplete: (success: boolean) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    const response = await fetch('/api/danger-zone/destroy-all/stream', { signal });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    if (!reader) throw new Error('Response body is not readable');
    const buffer = { current: '' };
    let exitCode: number | null = null;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const code = processStreamChunk(buffer, chunk, onData);
        if (code !== null) exitCode = code;
      }
      if (exitCode === null) exitCode = flushStreamBuffer(buffer, onData);
      onComplete(exitCode === 0);
    } catch (error) {
      onData(`\nError: ${error}\n`);
      onComplete(false);
    }
  },

  hardReset: async (): Promise<HardResetResult> => {
    const response = await axios.post<HardResetResult>('/api/danger-zone/hard-reset');
    return response.data;
  },
};
