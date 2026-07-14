I need to examine the repository structure to understand the codebase and determine where to implement the obstacle layer toggle feature.

<list_directory>
<path>.</path>
</list_directory>

<list_directory>
<path>src</path>
</list_directory>

<search_files>
<path>.</path>
<regex>canvas|sim|obstacle</regex>
<case_sensitive>false</case_sensitive>
</search_files>

<read_file>
<path>src/App.tsx</path>
</read_file>

<read_file>
<path>src/components/Canvas.tsx</path>
</read_file>

<search_files>
<path>.</path>
<regex>layer|toggle</regex>
<case_sensitive>false</case_sensitive>
</search_files>

<list_directory>
<path>src/components</path>
</list_directory>

<read_file>
<path>src/components/Simulation.tsx</path>
</read_file>

<read_file>
<path>src/types/index.ts</path>
</read_file>

<search_files>
<path>.</path>
<regex>useSimulation|simulation</regex>
<case_sensitive>false</case_sensitive>
</search_files>

<read_file>
<path>src/hooks/useSimulation.ts</path>
</read_file>

<read_file>
<path>src/utils/physics.ts</path>
</read_file>

<list_directory>
<path>src</path>
<recursive>true</recursive>
</list_directory>

<read_file>
<path>src/components/Controls.tsx</path>
</read_file>

```typescript
import React, { useState } from 'react';
import Canvas from './components/Canvas';
import Controls from './components/Controls';
import Simulation from './components/Simulation';
import { Obstacle } from './types';

function App() {
  const [obstacles, setObstacles] = useState<Obstacle[]>([]);
  const [showObstacles, setShowObstacles] = useState(true);
  const [isDrawingMode, setIsDrawingMode] = useState(false);

  const handleAddObstacle = (obstacle: Obstacle) => {
    setObstacles(prev => [...prev, obstacle]);
  };

  const handleRemoveObstacle = (id: string) => {
    setObstacles(prev => prev.filter(obs => obs.id !== id));
  };

  const handleClearObstacles = () => {
    setObstacles([]);
  };

  const handleToggleObstacles = () => {
    setShowObstacles(prev => !prev);
  };

  return (
    <div className="app">
      <h1>Lappa Simulation</h1>
      <Controls
        onToggleObstacles={handleToggleObstacles}
        showObstacles={showObstacles}
        onClearObstacles={handleClearObstacles}
        isDrawingMode={isDrawingMode}
        onToggleDrawingMode={() => setIsDrawingMode(prev => !prev)}
      />
      <Simulation
        obstacles={showObstacles ? obstacles : []}
        onAddObstacle={handleAddObstacle}
        onRemoveObstacle={handleRemoveObstacle}
        isDrawingMode={isDrawingMode}
      />
    </div>
  );
}

export default App;
```