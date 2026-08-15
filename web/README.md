# AgentGate Web

Chinese P1 evaluation UI backed by the AgentGate REST API.

Stack:

- Vue 3
- TypeScript
- Vite
- Element Plus

The Web UI should call the AgentGate REST API. It should not import Python backend code directly.

Run `npm install`, then start FastAPI on port 8000 and run `npm run dev`. Use `npm run build` for a production build and `npm run test:e2e` for desktop/mobile checks.
