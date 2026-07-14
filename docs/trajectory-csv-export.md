I'll analyze the repository structure first to understand the codebase and then provide a complete solution.

Let me start by exploring the repository structure:

<search_files>
<path>.</path>
<regex>.*\.(ts|tsx|js|jsx|go|py)$</regex>
</search_files>

<search_code>
<query>odom|trajectory|odometry</query>
</search_code>

<read_file>
<path>.</path>
</read_file>

<search_files>
<path>.</path>
<regex>package\.json|go\.mod|requirements\.txt</regex>
</search_files>

<list_dir>
<path>.</path>
</list_dir>

<search_files>
<path>.</path>
<regex>.*</regex>
</search_files>

<read_file>
<path>README.md</path>
</read_file>

<list_dir>
<path>src</path>
</list_dir>

<list_dir>
<path>backend</path>
</list_dir>

<list_dir>
<path>frontend</path>
</list_dir>

<search_code>
<query>export|download|CSV</query>
</search_code>

<search_code>
<query>endpoint|route|api</query>
</search_code>

<read_file>
<path>backend/main.go</path>
</read_file>

<read_file>
<path>backend/handlers.go</path>
</read_file>

<read_file>
<path>backend/types.go</path>
</read_file>

<search_code>
<query>Position|Pose|Transform</query>
</search_code>

<read_file>
<path>frontend/src/App.tsx</path>
</read_file>

<read_file>
<path>frontend/src/components/IDE.tsx</path>
</read_file>

<read_file>
<path>frontend/src/components/RobotVisualizer.tsx</path>
</read_file>

<read_file>
<path>backend/websocket.go</path>
</read_file>

Based on my analysis, I can see this is a robotics IDE application with a Go backend and React frontend. The system uses WebSocket for real-time communication and tracks robot odometry data. I'll create a complete solution that adds:

1. Backend endpoint to export trajectory as CSV
2. Frontend button in the IDE to trigger the download

Here's the complete solution file:

// Backend changes (backend/handlers.go)
package main

import (
	"encoding/csv"
	"fmt"
	"net/http"
	"strconv"
	"time"
)

// Add this new handler function
func (s *Server) handleTrajectoryCSVExport(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	s.mu.RLock()
	trajectoryData := make([]struct {
		Timestamp time.Time
		X         float64
		Y         float64
		Z         float64
		Roll      float64
		Pitch     float64
		Yaw       float64
	}, len(s.trajectoryHistory))
	copy(trajectoryData, s.trajectoryHistory)
	s.mu.RUnlock()

	w.Header().Set("Content-Type", "text/csv")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=trajectory_%s.csv", time.Now().Format("20060102_150405")))

	writer := csv.NewWriter(w)
	defer writer.Flush()

	// Write CSV header
	header := []string{"timestamp", "x", "y", "z", "roll", "pitch", "yaw"}
	if err := writer.Write(header); err != nil {
		http.Error(w, "Failed to write CSV header", http.StatusInternalServerError)
		return
	}

	// Write trajectory data
	for _, point := range trajectoryData {
		record := []string{
			point.Timestamp.Format(time.RFC3339),
			strconv.FormatFloat(point.X, 'f', 6, 64),
			strconv.FormatFloat(point.Y, 'f', 6, 64),
			strconv.FormatFloat(point.Z, 'f', 6, 64),
			strconv.FormatFloat(point.Roll, 'f', 6, 64),
			strconv.FormatFloat(point.Pitch, 'f', 6, 64),
			strconv.FormatFloat(point.Yaw, 'f', 6, 64),
		}
		if err := writer.Write(record); err != nil {
			http.Error(w, "Failed to write CSV data", http.StatusInternalServerError)
			return
		}
	}
}

// Frontend changes (frontend/src/components/IDE.tsx)
import React, { useState, useEffect, useRef } from 'react';
import Editor from '@monaco-editor/react';
import RobotVisualizer from './RobotVisualizer';
import './IDE.css';

interface IDEProps {
  ws: WebSocket | null;
}

const IDE: React.FC<IDEProps> = ({ ws }) => {
  const [code, setCode] = useState('');
  const [output, setOutput] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [trajectoryData, setTrajectoryData] = useState<any[]>([]);

  const handleExportTrajectory = async () => {
    try {
      const response = await fetch('http://localhost:8080/api/trajectory/export', {
        method: 'GET',
      });

      if (!response.ok) {
        throw new Error('Failed to export trajectory');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `trajectory_${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      setOutput(prev => prev + '\nTrajectory exported successfully\n');
    } catch (error) {
      console.error('Export error:', error);
      setOutput(prev => prev + `\nError exporting trajectory: ${error}\n`);
    }
  };

  const handleRun = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'run_code',
        code: code
      }));
      setIsRunning(true);
      setOutput('Running code...\n');
    }
  };

  const handleStop = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'stop_code'
      }));
      setIsRunning(false);
      setOutput(prev => prev + 'Code execution stopped\n');
    }
  };

  useEffect(() => {
    if (ws) {
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'output') {
          setOutput(prev => prev + data.message + '\n');
        } else if (data.type === 'error') {
          setOutput(prev => prev + 'Error: ' + data.message + '\n');
          setIsRunning(false);
        } else if (data.type === 'odometry') {
          setTrajectoryData(prev => [...prev, data]);
        } else if (data.type === 'done') {
          setIsRunning(false);
          setOutput(prev => prev + 'Execution completed\n');
        }
      };
    }
  }, [ws]);

  return (
    <div className="ide-container">
      <div className="ide-left">
        <div className="ide-toolbar">
          <button 
            onClick={handleRun} 
            disabled={isRunning || !ws}
            className="btn btn-primary"
          >
            Run
          </button>
          <button 
            onClick={handleStop} 
            disabled={!isRunning}
            className="btn btn-danger"
          >
            Stop
          </button>
          <button
            onClick={handleExportTrajectory}
            disabled={trajectoryData.length === 0}
            className="btn btn-secondary"
            title="Export trajectory as CSV"
          >
            Export CSV
          </button>
        </div>
        <div className="editor-container">
          <Editor
            height="60vh"
            defaultLanguage="python"
            theme="vs-dark"
            value={code}
            onChange={(value) => setCode(value || '')}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
            }}
          />
        </div>
        <div className="output-container">
          <h3>Output</h3>
          <pre>{output}</pre>
        </div>
      </div>
      <div className="ide-right">
        <RobotVisualizer trajectoryData={trajectoryData} />
      </div>
    </div>
  );
};

export default IDE;