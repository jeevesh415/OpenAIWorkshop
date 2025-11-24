# Magentic AI Chat - React Frontend

Professional React frontend (powered by Vite) for multi-agent AI assistant with real-time streaming.

## Features

- 🎨 **Clean Split UI**: Chat on the right, internal process on the left
- 📊 **Real-time Streaming**: See orchestrator planning and agent work live
- 🎯 **Collapsible Sections**: Expand/collapse orchestrator and individual agents
- 🎭 **Material-UI**: Professional, responsive design
- 🔄 **WebSocket**: Low-latency real-time updates
- 👁️ **Toggle Process View**: Show/hide internal thinking

## Setup

1. Install dependencies:

   ```bash
   cd react-frontend
   npm install
   ```

2. Configure backend URL (optional):

   Create `.env` file:

   ```bash
   VITE_BACKEND_URL=http://localhost:7000
   ```

   > `import.meta.env.VITE_*` is Vite's preferred naming convention. A legacy `REACT_APP_BACKEND_URL` is still read for backward compatibility, but new deployments should switch to `VITE_BACKEND_URL`.

3. Start the Vite development server:

   ```bash
   npm run dev
   ```

Vite prints both local and network URLs in the terminal (defaults to <http://localhost:3000> based on `vite.config.js`).

## Usage

1. Type your question in the input box
2. Press Enter or click Send
3. Watch the internal process on the left (orchestrator planning, agents working)
4. See the final answer in the main chat area
5. Click the eye icon to hide/show the internal process panel

## Production Build

```bash
npm run build

# Optional: preview the optimized build locally
npm run preview
```

The optimized assets are emitted to the `dist/` directory (Vite default).

## Docker (optional)

Build the static assets inside a container (override the backend URL at build time if needed):

```bash
docker build -t magentic-chat-ui \
   --build-arg VITE_BACKEND_URL=http://localhost:7000 \
   .
```

Run the optimized bundle with `npx serve` inside the container:

```bash
docker run --rm -p 3000:3000 magentic-chat-ui
```

Open <http://localhost:3000>. Because Vite inlines env vars during `npm run build`, changing the backend URL requires rebuilding the image with a different `--build-arg` value.
