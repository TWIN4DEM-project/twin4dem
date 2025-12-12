import {useEffect, useRef, useState} from 'react';
import './App.scss';

// --- Types mirroring the Pydantic models on the backend ---
type Party = "majority" | "opposition" | "independent";

interface MinisterConfig {
  id: number;
  type: 'Minister';
  party: Party;
  influence: number; // [0, 1]
  weights: [number, number, number, number, number, number];
  opinion: 0 | 1;
  support1: 0 | 1;
  support2: 0 | 1;
  is_pm: boolean;
}

interface GovernmentConfig {
  ministers: MinisterConfig[];
  kgov: number; // >= 1
  pact: number; // [0, 1]
  alpha: number; // [0, 1]
  epsilon: number; // >= 0
  gamma: number; // > 0
}

interface GovernmentConfigEnvelope {
  __pydantic_model__: 'GovernmentConfig';
  data: GovernmentConfig;
}

// Example config we send immediately when the WebSocket connection opens.
// Adjust these values as needed to match your backend expectations.
const sampleConfig: GovernmentConfig = {
  kgov: 3,
  pact: 0.7,
  alpha: 0.5,
  epsilon: 0.1,
  gamma: 1.0,
  ministers: [
    {
      id: 1,
      type: 'Minister',
      party: 'majority',
      influence: 0.9,
      weights: [1, 0, 0, 0, 0, 0],
      opinion: 1,
      support1: 1,
      support2: 1,
      is_pm: true,
    },
    {
      id: 2,
      type: 'Minister',
      party: 'majority',
      influence: 0.6,
      weights: [0, 1, 0, 0, 0, 0],
      opinion: 1,
      support1: 1,
      support2: 0,
      is_pm: false,
    },
    {
      id: 3,
      type: 'Minister',
      party: 'opposition',
      influence: 0.4,
      weights: [0, 0, 1, 0, 0, 0],
      opinion: 0,
      support1: 0,
      support2: 0,
      is_pm: false,
    },
  ],
};
const sampleInput: GovernmentConfigEnvelope = {
    __pydantic_model__: "GovernmentConfig",
    data: sampleConfig
}

function App() {
    const [messages, setMessages] = useState<Array<unknown>>([]);
    const [lastError, setLastError] = useState<string | null>(null);
    const [sendDisabled, setSendDisabled] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        const ws = new WebSocket(`ws://${window.location.host}/ws/executive/1/`);
        wsRef.current = ws;
        ws.onopen = () => {
            console.log('WebSocket connected');
        };
        ws.onmessage = (event: MessageEvent) => {
            try {
                const parsed = JSON.parse(event.data);

                // Handle status messages
                if (parsed && parsed.status === "task started") {
                    setSendDisabled(true);
                    return;
                }
                if (parsed && parsed.status === "task completed") {
                    setSendDisabled(false);
                    return;
                }

                // Otherwise add to visible messages
                setMessages(prev => [...prev, parsed]);
            } catch (err) {
                console.error('Failed to parse WebSocket message', err);
                setLastError('Failed to parse WebSocket message');
            }
        };
        ws.onerror = (event) => {
            console.error('WebSocket error observed:', event);
            setLastError(`WebSocket error: ${event}`);
        };
        ws.onclose = () => {
            console.log('WebSocket disconnected');
        };
    }, []);

    const handleSendSample = () => {
        setLastError(null);
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            setLastError('WebSocket is not connected');
            return;
        }
        try {
            ws.send(JSON.stringify(sampleInput));
        } catch (err) {
            console.error('Failed to send sample input', err);
            setLastError('Failed to send sample input');
        }
    };

    return (
        <div className="App">
            <h1>Sample Government Simulation</h1>
            {lastError && <p style={{color: 'red'}}>{lastError}</p>}

            <div className="config-layout-row">
                <div className="config-table-container">
                    <h2>GovernmentConfig</h2>
                    <table className="config-table">
                        <thead>
                        <tr>
                            <th>Property</th>
                            <th>Value</th>
                        </tr>
                        </thead>
                        <tbody>
                        <tr>
                            <td>kgov</td>
                            <td>{sampleConfig.kgov}</td>
                        </tr>
                        <tr>
                            <td>pact</td>
                            <td>{sampleConfig.pact}</td>
                        </tr>
                        <tr>
                            <td>alpha</td>
                            <td>{sampleConfig.alpha}</td>
                        </tr>
                        <tr>
                            <td>epsilon</td>
                            <td>{sampleConfig.epsilon}</td>
                        </tr>
                        <tr>
                            <td>gamma</td>
                            <td>{sampleConfig.gamma}</td>
                        </tr>
                        <tr>
                            <td>ministers (count)</td>
                            <td>{sampleConfig.ministers.length}</td>
                        </tr>
                        </tbody>
                    </table>
                </div>

                <div className="ministers-table-container">
                    <h2>Ministers</h2>
                    <table className="ministers-table">
                        <thead>
                        <tr>
                            <th>id</th>
                            <th>type</th>
                            <th>party</th>
                            <th>influence</th>
                            <th>weights</th>
                            <th>opinion</th>
                            <th>support1</th>
                            <th>support2</th>
                            <th>is_pm</th>
                        </tr>
                        </thead>
                        <tbody>
                        {sampleConfig.ministers.map((m) => (
                            <tr key={m.id}>
                                <td>{m.id}</td>
                                <td>{m.type}</td>
                                <td>{m.party}</td>
                                <td>{m.influence}</td>
                                <td>{m.weights.join(', ')}</td>
                                <td>{m.opinion}</td>
                                <td>{m.support1}</td>
                                <td>{m.support2}</td>
                                <td>{m.is_pm ? 'true' : 'false'}</td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <div style={{ margin: '1.5rem 0' }}>
                <button type="button" onClick={handleSendSample} disabled={sendDisabled}>
                    {sendDisabled ? "Running..." : "Send sample config"}
                </button>
            </div>

            <h2>Raw Messages</h2>
            {messages.length === 0 ? (
                <p>No messages received yet.</p>
            ) : (
                <ul>
                    {messages.map((msg, idx) => (
                        <li key={idx} style={{marginBottom: '0.75rem', textAlign: 'left'}}>
                            <pre>{JSON.stringify(msg, null, 2)}</pre>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

export default App;
