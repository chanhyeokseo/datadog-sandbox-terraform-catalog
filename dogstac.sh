#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
IMAGE="dogstac/dogstac:latest"
CONTAINER_NAME="dogstac"

detect_runtime() {
    if command -v docker &>/dev/null; then
        RUNTIME="docker"
    elif command -v podman &>/dev/null; then
        RUNTIME="podman"
    else
        echo "Error: Neither docker nor podman found. Please install one of them."
        exit 1
    fi
    echo "Using runtime: ${RUNTIME}"
}

load_config() {
    TFRUNNER_PORT=$(grep -E '^TFRUNNER_PORT=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
    TFRUNNER_PORT=${TFRUNNER_PORT:-7621}
    MCP_PORT=$(grep -E '^MCP_PORT=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
    MCP_PORT=${MCP_PORT:-7622}
    TERRAFORM_DATA_PATH=$(grep -E '^TERRAFORM_DATA_PATH=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
    TERRAFORM_DATA_PATH=${TERRAFORM_DATA_PATH:-./terraform-data}
    if [[ "${TERRAFORM_DATA_PATH}" == ./* || "${TERRAFORM_DATA_PATH}" == ../* ]]; then
        TERRAFORM_DATA_PATH="${SCRIPT_DIR}/${TERRAFORM_DATA_PATH}"
    fi
}

select_option() {
    local prompt="$1"
    shift
    local options=("$@")
    local selected=0
    local count=${#options[@]}

    printf "%s\n\n" "${prompt}"

    stty -echo 2>/dev/null
    trap 'stty echo 2>/dev/null' EXIT

    while true; do
        for i in "${!options[@]}"; do
            if [[ $i -eq $selected ]]; then
                printf "\r\033[K  \033[1;36m> %s\033[0m\n" "${options[$i]}"
            else
                printf "\r\033[K    %s\n" "${options[$i]}"
            fi
        done

        IFS= read -rsn1 key
        if [[ "${key}" == $'\x1b' ]]; then
            read -rsn2 rest
            key+="${rest}"
        fi

        case "${key}" in
            $'\x1b[A') ((selected > 0)) && ((selected--)) ;;
            $'\x1b[B') ((selected < count - 1)) && ((selected++)) ;;
            "") break ;;
        esac

        printf "\033[%dA" "${count}"
    done

    stty echo 2>/dev/null
    trap - EXIT
    SELECTED_INDEX=${selected}
}

load_existing_env() {
    PREV_AWS_PROFILE=$(grep -E '^AWS_PROFILE=.+' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
    PREV_AWS_ACCESS_KEY=$(grep -E '^AWS_ACCESS_KEY_ID=.+' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
    PREV_AWS_SECRET_KEY=$(grep -E '^AWS_SECRET_ACCESS_KEY=.+' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
    PREV_AWS_SESSION_TOKEN=$(grep -E '^AWS_SESSION_TOKEN=.+' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
    PREV_DOGSTAC_SALT=$(grep -E '^DOGSTAC_SALT=.+' "${ENV_FILE}" 2>/dev/null | cut -d= -f2 || true)
}

prompt_with_default() {
    local prompt="$1" default="$2" result
    if [[ -n "${default}" ]]; then
        read -rp "${prompt} [${default}]: " result
        echo "${result:-${default}}"
    else
        read -rp "${prompt}: " result
        echo "${result}"
    fi
}

setup_env() {
    local prev_profile="" prev_access_key="" prev_secret_key="" prev_session_token="" prev_salt=""
    if [[ -f "${ENV_FILE}" ]]; then
        load_existing_env
        prev_profile="${PREV_AWS_PROFILE}"
        prev_access_key="${PREV_AWS_ACCESS_KEY}"
        prev_secret_key="${PREV_AWS_SECRET_KEY}"
        prev_session_token="${PREV_AWS_SESSION_TOKEN}"
        prev_salt="${PREV_DOGSTAC_SALT}"
    fi

    echo "============================================"
    echo "  DogSTAC Initial Setup"
    echo "============================================"
    echo ""

    echo "Step 1: Choose AWS authentication type"
    select_option "  Use arrow keys to select, Enter to confirm:" \
        "AWS SSO    - Uses a named profile from ~/.aws/config" \
        "AWS IAM    - Uses static access key / secret key pair"
    local auth_type=$((SELECTED_INDEX + 1))
    echo ""

    local aws_profile="" aws_access_key="" aws_secret_key="" aws_session_token=""
    if [[ "${auth_type}" == "1" ]]; then
        echo "Step 2: Enter AWS Profile"
        echo "  The profile name configured in ~/.aws/config via 'aws configure sso'."
        echo "  Run 'aws configure list-profiles' to see available profiles."
        echo ""
        aws_profile=$(prompt_with_default "AWS_PROFILE" "${prev_profile}")
        if [[ -z "${aws_profile}" ]]; then
            echo "Error: AWS_PROFILE cannot be empty."
            exit 1
        fi
    else
        echo "Step 2: Enter AWS IAM credentials"
        echo "  Static credentials for an IAM user with permissions for"
        echo "  EC2, EKS, ECS, SSM Parameter Store, and related services."
        echo ""
        aws_access_key=$(prompt_with_default "AWS_ACCESS_KEY_ID" "${prev_access_key}")
        if [[ -z "${aws_access_key}" ]]; then
            echo "Error: AWS_ACCESS_KEY_ID cannot be empty."
            exit 1
        fi
        if [[ -n "${prev_secret_key}" ]]; then
            local masked="${prev_secret_key:0:4}****"
            read -rsp "AWS_SECRET_ACCESS_KEY [${masked}]: " aws_secret_key
            echo ""
            aws_secret_key="${aws_secret_key:-${prev_secret_key}}"
        else
            read -rsp "AWS_SECRET_ACCESS_KEY (hidden): " aws_secret_key
            echo ""
        fi
        if [[ -z "${aws_secret_key}" ]]; then
            echo "Error: AWS_SECRET_ACCESS_KEY cannot be empty."
            exit 1
        fi
        aws_session_token=$(prompt_with_default "AWS_SESSION_TOKEN (optional, press Enter to skip)" "${prev_session_token}")
    fi
    echo ""

    echo "Step 3: Enter DOGSTAC_SALT"
    echo "  A long random string used as encryption salt for stored configurations."
    echo "  This value must remain consistent across container restarts."
    if [[ -z "${prev_salt}" ]]; then
        echo "  Example: $(openssl rand -hex 32 2>/dev/null || echo 'any-long-random-string-at-least-32-chars')"
    fi
    echo ""
    local dogstac_salt
    dogstac_salt=$(prompt_with_default "DOGSTAC_SALT" "${prev_salt}")
    if [[ -z "${dogstac_salt}" ]]; then
        echo "Error: DOGSTAC_SALT cannot be empty."
        exit 1
    fi
    echo ""

    cat > "${ENV_FILE}" <<ENVFILE
AWS_PROFILE=${aws_profile}
AWS_ACCESS_KEY_ID=${aws_access_key}
AWS_SECRET_ACCESS_KEY=${aws_secret_key}
AWS_SESSION_TOKEN=${aws_session_token}

DOGSTAC_SALT=${dogstac_salt}

USE_PARAMETER_STORE=true
TERRAFORM_DIR=/app/terraform
LOG_LEVEL=INFO

TFRUNNER_PORT=7621
MCP_PORT=7622
ENVFILE

    echo ".env file created at ${ENV_FILE}"
    echo "============================================"
    echo ""
}

validate_env() {
    if [[ ! -f "${ENV_FILE}" ]]; then
        echo "Error: .env file not found. Run './dogstac.sh init' first."
        exit 1
    fi

    local has_profile has_access_key
    has_profile=$(grep -E '^AWS_PROFILE=.+' "${ENV_FILE}" 2>/dev/null || true)
    has_access_key=$(grep -E '^AWS_ACCESS_KEY_ID=.+' "${ENV_FILE}" 2>/dev/null || true)

    if [[ -z "${has_profile}" && -z "${has_access_key}" ]]; then
        echo "Error: AWS credentials not configured in .env"
        echo "Run './dogstac.sh init' to reconfigure."
        exit 1
    fi
}

run_container() {
    validate_env
    load_config

    local pull="${1:-true}"
    if [[ "${pull}" == "true" ]]; then
        echo "Pulling latest image: ${IMAGE}"
        ${RUNTIME} pull "${IMAGE}"
    else
        echo "Skipping image pull (using local image)"
    fi

    if ${RUNTIME} inspect "${CONTAINER_NAME}" &>/dev/null; then
        echo "Removing existing container: ${CONTAINER_NAME}"
        ${RUNTIME} rm -f "${CONTAINER_NAME}" >/dev/null
    fi

    echo "Starting container: ${CONTAINER_NAME}"
    ${RUNTIME} run -d \
        --name "${CONTAINER_NAME}" \
        --env-file "${ENV_FILE}" \
        -p "${TFRUNNER_PORT}:${TFRUNNER_PORT}" \
        -p "${MCP_PORT}:${MCP_PORT}" \
        -v "${TERRAFORM_DATA_PATH}:/app/terraform" \
        -v "${HOME}/.aws:/root/.aws" \
        --restart unless-stopped \
        "${IMAGE}"

    echo "Container ${CONTAINER_NAME} started successfully."
    echo "  TFRunner: http://localhost:${TFRUNNER_PORT}"
    echo "  MCP:      http://localhost:${MCP_PORT}"
}

cmd_init() {
    if [[ -f "${ENV_FILE}" ]]; then
        echo "Existing .env found at ${ENV_FILE}"
        read -rp "Overwrite? [y/N]: " confirm
        if [[ "${confirm}" != [yY] ]]; then
            echo "Aborted."
            return
        fi
    fi
    setup_env
    run_container true
}

cmd_start() { run_container true; }

cmd_start_no_update() { run_container false; }

cmd_stop() {
    if ! ${RUNTIME} inspect "${CONTAINER_NAME}" &>/dev/null; then
        echo "Container ${CONTAINER_NAME} does not exist."
        return
    fi
    echo "Stopping container: ${CONTAINER_NAME}"
    ${RUNTIME} stop "${CONTAINER_NAME}"
    echo "Container ${CONTAINER_NAME} stopped."
}

cmd_delete() {
    if ! ${RUNTIME} inspect "${CONTAINER_NAME}" &>/dev/null; then
        echo "Container ${CONTAINER_NAME} does not exist."
        return
    fi
    echo "Stopping and removing container: ${CONTAINER_NAME}"
    ${RUNTIME} rm -f "${CONTAINER_NAME}"
    echo "Container ${CONTAINER_NAME} deleted."
}

cmd_status() {
    if ! ${RUNTIME} inspect "${CONTAINER_NAME}" &>/dev/null; then
        echo "Container ${CONTAINER_NAME} does not exist."
        return
    fi
    ${RUNTIME} ps -a --filter "name=^${CONTAINER_NAME}$" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

cmd_logs() {
    if ! ${RUNTIME} inspect "${CONTAINER_NAME}" &>/dev/null; then
        echo "Container ${CONTAINER_NAME} does not exist."
        return
    fi
    ${RUNTIME} logs -f "${CONTAINER_NAME}"
}

cmd_mcp_init() {
    load_config
    local mcp_url="http://localhost:${MCP_PORT}/sse"

    echo "Setup MCP server connection"
    select_option "  Choose your AI coding tool:" \
        "Claude Code  - Register via claude CLI" \
        "Cursor       - Register via .cursor/mcp.json"
    local tool_choice=${SELECTED_INDEX}
    echo ""

    if [[ ${tool_choice} -eq 0 ]]; then
        if ! command -v claude &>/dev/null; then
            echo "Error: 'claude' CLI not found."
            echo "Install Claude Code first: https://docs.anthropic.com/en/docs/claude-code"
            exit 1
        fi
        echo "Registering MCP server with Claude Code..."
        claude mcp add dogstac --transport sse "${mcp_url}"
        echo "Done. MCP server 'dogstac' registered in Claude Code."
    else
        if ! command -v cursor &>/dev/null; then
            echo "Error: 'cursor' CLI not found."
            echo "Install Cursor first, then enable the 'cursor' CLI command:"
            echo "  Cursor > Command Palette > 'Shell Command: Install cursor command'"
            exit 1
        fi
        local mcp_json="${HOME}/.cursor/mcp.json"
        mkdir -p "${HOME}/.cursor"

        if [[ -f "${mcp_json}" ]]; then
            local has_dogstac
            has_dogstac=$(grep -c '"dogstac"' "${mcp_json}" 2>/dev/null || true)
            if [[ "${has_dogstac}" -gt 0 ]]; then
                echo "MCP server 'dogstac' already configured in ${mcp_json}"
                return
            fi

            local tmp="${mcp_json}.tmp"
            python3 -c "
import json, sys
with open('${mcp_json}') as f:
    data = json.load(f)
data.setdefault('mcpServers', {})['dogstac'] = {'url': '${mcp_url}'}
with open('${tmp}', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
            mv "${tmp}" "${mcp_json}"
            echo "Added 'dogstac' to existing ${mcp_json}"
        else
            cat > "${mcp_json}" <<MCPJSON
{
  "mcpServers": {
    "dogstac": {
      "url": "${mcp_url}"
    }
  }
}
MCPJSON
            echo "Created ${mcp_json}"
        fi
        echo "Restart Cursor or run 'Developer: Reload Window' to activate."
    fi
}

cmd_alias() {
    local shell_rc=""
    case "${SHELL}" in
        */zsh)  shell_rc="${HOME}/.zshrc" ;;
        */bash) shell_rc="${HOME}/.bashrc" ;;
        *)      shell_rc="${HOME}/.profile" ;;
    esac

    local alias_line="alias dogstac='${SCRIPT_DIR}/dogstac.sh'"

    if grep -qF "alias dogstac=" "${shell_rc}" 2>/dev/null; then
        sed -i '' "/alias dogstac=/d" "${shell_rc}"
        echo "Removed old alias from ${shell_rc}"
    fi
    echo "" >> "${shell_rc}"
    echo "${alias_line}" >> "${shell_rc}"
    echo "Added alias to ${shell_rc}:"
    echo "  ${alias_line}"
    echo ""
    echo "Run the following to activate now:"
    echo "  source ${shell_rc}"
}

usage() {
    cat <<EOF
Usage: $(basename "$0") <command>

Commands:
    init            Interactive setup (.env) and start the container
    start           Pull latest image and start the container
    start-no-update Start the container without pulling the latest image
    stop            Stop the running container
    delete          Stop and remove the container
    status          Show container status
    logs            Follow container logs (Ctrl+C to exit)
    mcp-init        Register DogSTAC MCP server with Claude Code or Cursor
    alias           Add 'dogstac' alias to your shell config
    help            Show this help message
EOF
}

detect_runtime

case "${1:-help}" in
    init)            cmd_init ;;
    start)           cmd_start ;;
    start-no-update) cmd_start_no_update ;;
    stop)            cmd_stop ;;
    delete)          cmd_delete ;;
    status)          cmd_status ;;
    logs)            cmd_logs ;;
    mcp-init)        cmd_mcp_init ;;
    alias)           cmd_alias ;;
    help)            usage ;;
    *)               echo "Unknown command: $1" >&2; usage; exit 1 ;;
esac
