interface CausalEvent {
  id: string;
  timestamp: number;
  causeId?: string;
  effectIds: string[];
  description: string;
  tags: string[];
  confidence: number;
}

interface CausalQuery {
  type: 'counterfactual' | 'temporal' | 'chain';
  eventId?: string;
  timestamp?: number;
  condition?: Record<string, any>;
  depth?: number;
}

interface FleetNode {
  id: string;
  lastSeen: number;
  eventCount: number;
  version: string;
}

class CausalMemory {
  private events: Map<string, CausalEvent>;
  private fleet: Map<string, FleetNode>;
  private graph: Map<string, Set<string>>;

  constructor() {
    this.events = new Map();
    this.fleet = new Map();
    this.graph = new Map();
  }

  addEvent(event: CausalEvent): void {
    this.events.set(event.id, event);
    
    if (event.causeId) {
      if (!this.graph.has(event.causeId)) {
        this.graph.set(event.causeId, new Set());
      }
      this.graph.get(event.causeId)!.add(event.id);
    }
    
    event.effectIds.forEach(effectId => {
      if (!this.graph.has(event.id)) {
        this.graph.set(event.id, new Set());
      }
      this.graph.get(event.id)!.add(effectId);
    });
  }

  getEffects(causeId: string, depth: number = 1): CausalEvent[] {
    const results: CausalEvent[] = [];
    const visited = new Set<string>();
    const queue: {id: string, level: number}[] = [{id: causeId, level: 0}];

    while (queue.length > 0) {
      const current = queue.shift()!;
      
      if (visited.has(current.id) || current.level > depth) continue;
      visited.add(current.id);

      const event = this.events.get(current.id);
      if (event && current.level > 0) {
        results.push(event);
      }

      const effects = this.graph.get(current.id);
      if (effects) {
        effects.forEach(effectId => {
          queue.push({id: effectId, level: current.level + 1});
        });
      }
    }

    return results;
  }

  queryCounterfactual(eventId: string, condition: Record<string, any>): CausalEvent[] {
    const event = this.events.get(eventId);
    if (!event) return [];

    return Array.from(this.events.values()).filter(e => {
      return e.timestamp < event.timestamp && 
             Object.keys(condition).every(key => 
               (e as any)[key] === condition[key]
             );
    });
  }

  getTemporalEvents(start: number, end: number): CausalEvent[] {
    return Array.from(this.events.values())
      .filter(e => e.timestamp >= start && e.timestamp <= end)
      .sort((a, b) => a.timestamp - b.timestamp);
  }

  getCausalChain(eventId: string, maxDepth: number = 10): CausalEvent[] {
    const chain: CausalEvent[] = [];
    let currentId: string | undefined = eventId;
    let depth = 0;

    while (currentId && depth < maxDepth) {
      const event = this.events.get(currentId);
      if (!event) break;
      
      chain.push(event);
      currentId = event.causeId;
      depth++;
    }

    return chain.reverse();
  }

  updateFleet(nodeId: string, version: string): void {
    this.fleet.set(nodeId, {
      id: nodeId,
      lastSeen: Date.now(),
      eventCount: this.events.size,
      version
    });
  }

  getFleetStatus(): FleetNode[] {
    const now = Date.now();
    return Array.from(this.fleet.values())
      .filter(node => now - node.lastSeen < 300000)
      .sort((a, b) => a.lastSeen - b.lastSeen);
  }
}

const causalMemory = new CausalMemory();

const htmlResponse = (content: string): Response => {
  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Causal Memory</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: 'Inter', sans-serif; 
      background: #0a0a0f; 
      color: #e5e5e5; 
      line-height: 1.6;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .container { 
      max-width: 1200px; 
      margin: 0 auto; 
      padding: 2rem; 
      flex: 1;
    }
    header { 
      border-bottom: 1px solid #1f1f2e; 
      padding-bottom: 1.5rem;
      margin-bottom: 2rem;
    }
    h1 { 
      color: #dc2626; 
      font-size: 2.5rem; 
      font-weight: 700;
      margin-bottom: 0.5rem;
    }
    .subtitle { 
      color: #94a3b8; 
      font-size: 1.1rem;
      font-weight: 400;
    }
    .grid { 
      display: grid; 
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
      gap: 1.5rem; 
      margin-bottom: 3rem;
    }
    .card { 
      background: #11111a; 
      border: 1px solid #1f1f2e; 
      border-radius: 8px; 
      padding: 1.5rem;
      transition: transform 0.2s, border-color 0.2s;
    }
    .card:hover {
      transform: translateY(-2px);
      border-color: #dc2626;
    }
    .card h3 { 
      color: #dc2626; 
      margin-bottom: 1rem; 
      font-weight: 600;
    }
    .endpoint { 
      background: #1a1a2e; 
      padding: 0.75rem; 
      border-radius: 4px; 
      margin: 0.5rem 0; 
      font-family: monospace;
      border-left: 3px solid #dc2626;
    }
    .stats { 
      display: flex; 
      gap: 2rem; 
      margin-top: 1rem;
    }
    .stat { 
      text-align: center;
    }
    .stat-value { 
      font-size: 1.5rem; 
      font-weight: 700; 
      color: #dc2626;
    }
    .stat-label { 
      font-size: 0.875rem; 
      color: #94a3b8;
    }
    footer { 
      background: #11111a; 
      border-top: 1px solid #1f1f2e; 
      padding: 2rem;
      margin-top: auto;
    }
    .fleet-footer {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }
    .fleet-nodes {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }
    .node-indicator {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #10b981;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    .version { 
      color: #94a3b8; 
      font-size: 0.875rem;
    }
    .api-link {
      color: #60a5fa;
      text-decoration: none;
      transition: color 0.2s;
    }
    .api-link:hover {
      color: #dc2626;
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Causal Memory</h1>
      <p class="subtitle">Distributed causal reasoning engine with temporal analysis and counterfactual queries</p>
      <div class="stats">
        <div class="stat">
          <div class="stat-value" id="eventCount">0</div>
          <div class="stat-label">Causal Events</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="fleetCount">0</div>
          <div class="stat-label">Active Nodes</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="graphSize">0</div>
          <div class="stat-label">Graph Edges</div>
        </div>
      </div>
    </header>
    
    <main>
      <div class="grid">
        <div class="card">
          <h3>Record Cause</h3>
          <p>Register new causal events with temporal metadata</p>
          <div class="endpoint">POST /api/cause</div>
          <pre><code>{
  "id": "event_123",
  "causeId": "event_122",
  "description": "Service latency spike",
  "tags": ["latency", "service-a"]
}</code></pre>
        </div>
        
        <div class="card">
          <h3>Query Effects</h3>
          <p>Retrieve downstream effects from any cause</p>
          <div class="endpoint">GET /api/effects?causeId=...</div>
          <div class="endpoint">GET /api/effects?causeId=...&depth=3</div>
          <p>Depth parameter controls causal chain length</p>
        </div>
        
        <div class="card">
          <h3>Advanced Queries</h3>
          <p>Counterfactual and temporal reasoning</p>
          <div class="endpoint">POST /api/query</div>
          <pre><code>{
  "type": "counterfactual",
  "eventId": "event_123",
  "condition": {"tags": ["latency"]}
}</code></pre>
        </div>
      </div>
      
      <div class="card">
        <h3>API Documentation</h3>
        <p>Full API reference available at <a href="/api/docs" class="api-link">/api/docs</a></p>
        <p>Health check: <a href="/health" class="api-link">/health</a></p>
        <p>Fleet status: <a href="/api/fleet" class="api-link">/api/fleet</a></p>
      </div>
    </main>
  </div>
  
  <footer>
    <div class="fleet-footer">
      <div class="fleet-nodes">
        <div class="node-indicator"></div>
        <span>Causal Memory Fleet</span>
      </div>
      <div class="version">v1.0.0 | Causal Reasoning Engine</div>
      <div id="liveStats" class="version">Initializing...</div>
    </div>
  </footer>
  
  <script>
    async function updateStats() {
      try {
        const [eventsRes, fleetRes] = await Promise.all([
          fetch('/api/effects?causeId=root'),
          fetch('/api/fleet')
        ]);
        
        if (eventsRes.ok) {
          const events = await eventsRes.json();
          document.getElementById('eventCount').textContent = events.length || 0;
          document.getElementById('graphSize').textContent = 
            events.reduce((acc, e) => acc + (e.effectIds?.length || 0), 0);
        }
        
        if (fleetRes.ok) {
          const fleet = await fleetRes.json();
          document.getElementById('fleetCount').textContent = fleet.length || 0;
          document.getElementById('liveStats').textContent = 
            \`\${fleet.length} nodes | \${new Date().toLocaleTimeString()}\`;
        }
      } catch (e) {
        console.error('Stats update failed:', e);
      }
    }
    
    updateStats();
    setInterval(updateStats, 10000);
  </script>
</body>
</html>`;
  
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html;charset=UTF-8',
      'Content-Security-Policy': "default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; font-src https://fonts.gstatic.com;",
      'X-Frame-Options': 'DENY'
    }
  });
};

const handleRequest = async (request: Request): Promise<Response> => {
  const url = new URL(request.url);
  const path = url.pathname;

  if (path === '/' || path === '/dashboard') {
    return htmlResponse('');
  }

  if (path === '/health') {
    return new Response(JSON.stringify({ status: 'ok', timestamp: Date.now() }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (path === '/api/fleet') {
    const fleet = causalMemory.getFleetStatus();
    return new Response(JSON.stringify(fleet), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (path === '/api/cause' && request.method === 'POST') {
    try {
      const event: CausalEvent = await request.json();
      event.timestamp = event.timestamp || Date.now();
      event.confidence = event.confidence || 1.0;
      event.effectIds = event.effectIds || [];
      event.tags = event.tags || [];
      
      causalMemory.addEvent(event);
      
      const nodeId = request.headers.get('X-Node-ID') || 'unknown';
      const version = request.headers.get('X-Node-Version') || '1.0.0';
      causalMemory.updateFleet(nodeId, version);
      
      return new Response(JSON.stringify({ 
        success: true, 
        id: event.id,
        timestamp: event.timestamp 
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: 'Invalid event data' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }

  if (path === '/api/effects' && request.method === 'GET') {
    const causeId = url.searchParams.get('causeId') || 'root';
    const depth = parseInt(url.searchParams.get('depth') || '1');
    
    const effects = causalMemory.getEffects(causeId, depth);
    return new Response(JSON.stringify(effects), {
      headers: { 'Content-Type': 'application/json' }
    });
  }

  if (path === '/api/query' && request.method === 'POST') {
    try {
      const query: CausalQuery = await request.json();
      let results: CausalEvent[] = [];
      
      switch (query.type) {
        case 'counterfactual':
          if (query.eventId && query.condition) {
            results = causalMemory.queryCounterfactual(query.eventId, query.condition);
          }
          break;
        case 'temporal':
          if (query.timestamp) {
            const start = query.timestamp - 3600000;
            const end = query.timestamp;
            results = causalMemory.getTemporalEvents(start, end);
          }
          break;
        case 'chain':
          if (query.eventId) {
            results = causalMemory.getCausalChain(query.eventId, query.depth);
          }
          break;
      }
      
      return new Response(JSON.stringify(results), {
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: 'Invalid query' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }

  return new Response(JSON.stringify({ error: 'Not found' }), {
    status: 404,
    headers: { 'Content-Type': 'application/json' }
  });
};

export default {
  async fetch(request: Request, env: any, ctx: ExecutionContext): Promise<Response> {
    const response = await handleRequest(request);
    
    const headers = new Headers(response.headers);
    headers.set('X-Frame-Options', 'DENY');
    headers.set('Content-Security-Policy', 
      "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self'");
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers
    });
  }
};
