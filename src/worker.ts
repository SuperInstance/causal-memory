interface CausalEvent {
  id: string;
  timestamp: number;
  causeId?: string;
  action: string;
  agent: string;
  effect: string;
  confidence: number;
  metadata?: Record<string, any>;
}

interface CausalQuery {
  type: 'effects' | 'causes' | 'counterfactual' | 'chain';
  targetId?: string;
  startTime?: number;
  endTime?: number;
  agentFilter?: string[];
  actionFilter?: string[];
  intervention?: {
    eventId: string;
    alternativeAction: string;
  };
}

interface CausalGraph {
  events: Map<string, CausalEvent>;
  adjacency: Map<string, string[]>;
}

class CausalMemory {
  private graph: CausalGraph;
  private storage: KVNamespace;

  constructor(storage: KVNamespace) {
    this.graph = {
      events: new Map(),
      adjacency: new Map()
    };
    this.storage = storage;
  }

  async initialize() {
    try {
      const stored = await this.storage.get('causal_graph', 'json');
      if (stored && stored.events) {
        this.graph.events = new Map(Object.entries(stored.events));
        this.graph.adjacency = new Map(Object.entries(stored.adjacency));
      }
    } catch (e) {
      console.log('No existing graph found, starting fresh');
    }
  }

  async addEvent(event: CausalEvent): Promise<void> {
    this.graph.events.set(event.id, event);
    
    if (event.causeId) {
      const existing = this.graph.adjacency.get(event.causeId) || [];
      existing.push(event.id);
      this.graph.adjacency.set(event.causeId, existing);
    }
    
    await this.persist();
  }

  async getEffects(causeId: string, depth: number = 3): Promise<CausalEvent[]> {
    const results: CausalEvent[] = [];
    const visited = new Set<string>();
    
    const traverse = (currentId: string, currentDepth: number) => {
      if (currentDepth >= depth || visited.has(currentId)) return;
      
      visited.add(currentId);
      const children = this.graph.adjacency.get(currentId) || [];
      
      for (const childId of children) {
        const child = this.graph.events.get(childId);
        if (child) {
          results.push(child);
          traverse(childId, currentDepth + 1);
        }
      }
    };
    
    traverse(causeId, 0);
    return results;
  }

  async queryCausalChain(startId: string, endId?: string): Promise<CausalEvent[]> {
    const path: CausalEvent[] = [];
    const findPath = (currentId: string, targetId?: string): boolean => {
      const current = this.graph.events.get(currentId);
      if (!current) return false;
      
      path.push(current);
      
      if (targetId && currentId === targetId) return true;
      if (!targetId && !this.graph.adjacency.has(currentId)) return true;
      
      const children = this.graph.adjacency.get(currentId) || [];
      for (const childId of children) {
        if (findPath(childId, targetId)) return true;
      }
      
      path.pop();
      return false;
    };
    
    findPath(startId, endId);
    return path;
  }

  async simulateIntervention(eventId: string, alternativeAction: string): Promise<CausalEvent[]> {
    const original = this.graph.events.get(eventId);
    if (!original) return [];
    
    const simulated: CausalEvent[] = [];
    const affectedEvents = await this.getEffects(eventId, 5);
    
    affectedEvents.forEach(event => {
      simulated.push({
        ...event,
        effect: `[SIMULATED] ${event.effect}`,
        metadata: {
          ...event.metadata,
          simulatedFrom: eventId,
          originalAction: original.action,
          alternativeAction
        }
      });
    });
    
    return simulated;
  }

  async temporalQuery(startTime: number, endTime: number): Promise<CausalEvent[]> {
    const results: CausalEvent[] = [];
    
    for (const event of this.graph.events.values()) {
      if (event.timestamp >= startTime && event.timestamp <= endTime) {
        results.push(event);
      }
    }
    
    return results.sort((a, b) => a.timestamp - b.timestamp);
  }

  private async persist(): Promise<void> {
    const serialized = {
      events: Object.fromEntries(this.graph.events),
      adjacency: Object.fromEntries(this.graph.adjacency)
    };
    
    await this.storage.put('causal_graph', JSON.stringify(serialized));
  }
}

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
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            border-bottom: 1px solid #1a1a2e;
            padding-bottom: 20px;
            margin-bottom: 40px;
        }
        h1 {
            color: #ffffff;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .accent { color: #dc2626; }
        .subtitle {
            color: #94a3b8;
            font-size: 1.1rem;
            font-weight: 400;
        }
        .endpoints {
            background: #111827;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 40px;
            border-left: 4px solid #dc2626;
        }
        .endpoint {
            margin-bottom: 15px;
            padding: 12px;
            background: #1e293b;
            border-radius: 6px;
            font-family: 'Monaco', 'Consolas', monospace;
        }
        .method {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.85rem;
            margin-right: 10px;
        }
        .post { background: #059669; color: white; }
        .get { background: #2563eb; color: white; }
        .footer {
            margin-top: 60px;
            padding-top: 20px;
            border-top: 1px solid #1a1a2e;
            text-align: center;
            color: #64748b;
            font-size: 0.9rem;
        }
        .fleet-badge {
            display: inline-block;
            background: #1e293b;
            padding: 8px 16px;
            border-radius: 20px;
            margin-top: 10px;
            color: #dc2626;
            font-weight: 600;
        }
        code {
            background: #1e293b;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Causal <span class="accent">Memory</span></h1>
            <p class="subtitle">Track and query cause-effect chains across fleet actions</p>
        </header>
        
        <div class="endpoints">
            <h2 style="color: #ffffff; margin-bottom: 20px;">API Endpoints</h2>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <code>/api/cause</code>
                <p style="margin-top: 8px; color: #cbd5e1;">Record a causal event with action and effect</p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <code>/api/effects?causeId=:id&depth=:depth</code>
                <p style="margin-top: 8px; color: #cbd5e1;">Retrieve effects chain from a cause</p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <code>/api/query</code>
                <p style="margin-top: 8px; color: #cbd5e1;">Execute causal queries and simulations</p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <code>/health</code>
                <p style="margin-top: 8px; color: #cbd5e1;">Health check endpoint</p>
            </div>
        </div>
        
        <div class="footer">
            <p>Causal Reasoning Engine v1.0</p>
            <p>Track and query cause-effect chains across fleet actions</p>
            <div class="fleet-badge">Fleet Causal Intelligence</div>
        </div>
    </div>
</body>
</html>
  `;
  
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html;charset=UTF-8',
      'X-Frame-Options': 'DENY',
      'Content-Security-Policy': "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'none';"
    }
  });
};

const handleApiRequest = async (
  request: Request,
  causalMemory: CausalMemory,
  pathname: string,
  searchParams: URLSearchParams
): Promise<Response> => {
  const headers = {
    'Content-Type': 'application/json',
    'X-Frame-Options': 'DENY',
    'Content-Security-Policy': "default-src 'self'"
  };

  try {
    if (request.method === 'POST' && pathname === '/api/cause') {
      const event: CausalEvent = await request.json();
      
      if (!event.id || !event.action || !event.effect || !event.agent) {
        return new Response(JSON.stringify({ error: 'Missing required fields' }), {
          status: 400,
          headers
        });
      }
      
      event.timestamp = event.timestamp || Date.now();
      event.confidence = event.confidence || 1.0;
      
      await causalMemory.addEvent(event);
      
      return new Response(JSON.stringify({
        success: true,
        eventId: event.id,
        message: 'Causal event recorded'
      }), { headers });
    }

    if (request.method === 'GET' && pathname === '/api/effects') {
      const causeId = searchParams.get('causeId');
      const depth = parseInt(searchParams.get('depth') || '3');
      
      if (!causeId) {
        return new Response(JSON.stringify({ error: 'Missing causeId parameter' }), {
          status: 400,
          headers
        });
      }
      
      const effects = await causalMemory.getEffects(causeId, depth);
      
      return new Response(JSON.stringify({
        causeId,
        depth,
        effects,
        count: effects.length
      }), { headers });
    }

    if (request.method === 'POST' && pathname === '/api/query') {
      const query: CausalQuery = await request.json();
      
      let results: any[] = [];
      
      switch (query.type) {
        case 'effects':
          if (query.targetId) {
            results = await causalMemory.getEffects(query.targetId, 3);
          }
          break;
          
        case 'causes':
          if (query.startTime && query.endTime) {
            results = await causalMemory.temporalQuery(query.startTime, query.endTime);
          }
          break;
          
        case 'chain':
          if (query.targetId) {
            results = await causalMemory.queryCausalChain(query.targetId);
          }
          break;
          
        case 'counterfactual':
          if (query.intervention) {
            results = await causalMemory.simulateIntervention(
              query.intervention.eventId,
              query.intervention.alternativeAction
            );
          }
          break;
      }
      
      return new Response(JSON.stringify({
        queryType: query.type,
        results,
        count: results.length
      }), { headers });
    }

    if (request.method === 'GET' && pathname === '/health') {
      return new Response(JSON.stringify({
        status: 'healthy',
        timestamp: Date.now(),
        service: 'causal-memory'
      }), { headers });
    }

    return new Response(JSON.stringify({ error: 'Not found' }), {
      status: 404,
      headers
    });

  } catch (error) {
    console.error('API error:', error);
    return new Response(JSON.stringify({ 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    }), {
      status: 500,
      headers
    });
  }
};

export default {
  async fetch(request: Request, env: { CAUSAL_MEMORY: KVNamespace }, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const pathname = url.pathname;
    const searchParams = url.searchParams;
    
    const causalMemory = new CausalMemory(env.CAUSAL_MEMORY);
    await causalMemory.initialize();
    
    if (pathname === '/' || pathname === '') {
      return htmlResponse('');
    }
    
    if (pathname.startsWith('/api/') || pathname === '/health') {
      return handleApiRequest(request, causalMemory, pathname, searchParams);
    }
    
    return new Response('Not found', { status: 404 });
  }
};
