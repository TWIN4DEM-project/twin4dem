import {useEffect, useRef, useState} from 'react'
import reactLogo from '../assets/react.svg'
import viteLogo from '../assets/vite.svg'
import './App.css'

function App() {
    const [count, setCount] = useState(0)
    const [serverCount, setServerCount] = useState(0)
    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        const wsUrl = `ws://${window.location.host}/ws/simulation/1/`

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setServerCount(() => data.counter)
            } catch {
                console.error("failed to set counter")
            }
        };

        ws.onopen = () => console.log("WS connected");
        ws.onclose = () => console.log("WS closed");
        ws.onerror = (e) => console.error("WS error", e);

        return () => {
            ws.close();
        };
    }, []);

    const fireServerCount = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send("{}");
        }
    };

    return (
        <>
            <div>
                <a href="https://vite.dev" target="_blank">
                    <img src={viteLogo} className="logo" alt="Vite logo"/>
                </a>
                <a href="https://react.dev" target="_blank">
                    <img src={reactLogo} className="logo react" alt="React logo"/>
                </a>
            </div>
            <h1>Vite + React</h1>
            <div className="card">
                <button onClick={() => setCount((count) => count + 1)}>
                    count is {count}
                </button>
                <p>
                    Edit <code>src/App.tsx</code> and save to test HMR
                </p>
            </div>
            <div className="card">
                <button onClick={() => fireServerCount()}>
                    server count is {serverCount}
                </button>
            </div>
            <p className="read-the-docs">
                Click on the Vite and React logos to learn more
            </p>
        </>
    )
}

export default App
