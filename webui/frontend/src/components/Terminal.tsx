import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Terminal as XTerm } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import '../styles/Terminal.css';

const Terminal = () => {
  const { connectionId } = useParams<{ connectionId: string }>();
  const navigate = useNavigate();
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resourceInfo, setResourceInfo] = useState<any>(null);

  const sendResize = useCallback((ws: WebSocket) => {
    const fitAddon = fitAddonRef.current;
    const term = xtermRef.current;
    if (!fitAddon || !term || ws.readyState !== WebSocket.OPEN) return;
    fitAddon.fit();
    const dims = fitAddon.proposeDimensions();
    if (dims) {
      ws.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }));
    }
  }, []);

  useEffect(() => {
    const paramsStr = sessionStorage.getItem(`ssh_${connectionId}`);
    if (!paramsStr) {
      setError('Connection parameters not found');
      return;
    }

    const params = JSON.parse(paramsStr);
    setResourceInfo(params);
    document.title = `DogSTAC:${params.resourceName || connectionId}`;

    const term = new XTerm({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    if (terminalRef.current) {
      term.open(terminalRef.current);
      fitAddon.fit();
    }

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    const dims = fitAddon.proposeDimensions();
    const initCols = dims?.cols ?? 80;
    const initRows = dims?.rows ?? 24;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ssh/connect/${connectionId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      term.writeln('Establishing SSH connection...');
      
      ws.send(JSON.stringify({
        hostname: params.hostname,
        username: params.username || 'ec2-user',
        key_filename: params.keyFilename ?? undefined,
        port: params.port || 22,
        cols: initCols,
        rows: initRows,
      }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        
        switch (msg.type) {
          case 'status':
            term.writeln(`\r\n${msg.data}\r\n`);
            break;
          case 'connected':
            setConnected(true);
            term.writeln(`\r\n✅ ${msg.data}\r\n`);
            sendResize(ws);
            break;
          case 'output':
            term.write(msg.data);
            break;
          case 'error':
            const errorMsg = msg.data;
            const displayError = errorMsg.toLowerCase().includes('timed out') 
              ? `${errorMsg}, perhaps you didn't update the security group rules?`
              : errorMsg;
            setError(displayError);
            term.writeln(`\r\n❌ ${displayError}\r\n`);
            break;
        }
      } catch (e) {
        console.error('Error parsing message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      const errorMsg = 'Connection error';
      setError(errorMsg);
      term.writeln(`\r\n❌ ${errorMsg}\r\n`);
    };

    ws.onclose = () => {
      setConnected(false);
      term.writeln('\r\n⚠️  Connection closed\r\n');
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });

    const handleResize = () => sendResize(ws);

    window.addEventListener('resize', handleResize);

    let resizeObserver: ResizeObserver | undefined;
    if (terminalRef.current) {
      resizeObserver = new ResizeObserver(() => sendResize(ws));
      resizeObserver.observe(terminalRef.current);
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      resizeObserver?.disconnect();
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
      term.dispose();
    };
  }, [connectionId, sendResize]);

  const handleClose = async () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    
    try {
      await fetch(`/api/ssh/connections/${connectionId}`, {
        method: 'DELETE',
      });
    } catch (error) {
      console.error('Failed to close SSH connection:', error);
    }
    
    sessionStorage.removeItem(`ssh_${connectionId}`);
    if (window.opener) {
      window.close();
    } else {
      navigate('/');
    }
  };

  return (
    <div className="terminal-page">
      <header className="app-header">
        <div className="header-content" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          <img src="/logo.png" alt="DogSTAC" className="app-logo-header" />
          <h1>DogSTAC</h1>
        </div>
      </header>

      <div className="terminal-content">
        <div className="terminal-header">
          <div className="terminal-info">
            {resourceInfo && (
              <>
                <h2>{resourceInfo.resourceName}</h2>
                <div className="terminal-details">
                  <span className="detail-item">
                    <strong>Instance:</strong> {resourceInfo.instanceId || 'N/A'}
                  </span>
                  <span className="detail-item">
                    <strong>Host:</strong> {resourceInfo.hostname}
                  </span>
                  <span className="detail-item">
                    <strong>User:</strong> {resourceInfo.username || 'ec2-user'}
                  </span>
                  <span className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
                    {connected ? '● Connected' : '○ Disconnected'}
                  </span>
                </div>
              </>
            )}
          </div>
          <button onClick={handleClose} className="btn-close-terminal">
            Close Terminal
          </button>
        </div>
        
        {error && (
          <div className="terminal-error">
            ⚠️ {error}
          </div>
        )}
        
        <div className="terminal-container" ref={terminalRef} />
      </div>
    </div>
  );
};

export default Terminal;
