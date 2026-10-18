import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AeroGuardProvider } from "./hooks/useAeroGuard";
// Console typeface bundled locally (no runtime font CDN), OFL-1.1 licensed.
import "@fontsource/rajdhani/500.css";
import "@fontsource/rajdhani/600.css";
import "@fontsource/rajdhani/700.css";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing from index.html");

createRoot(root).render(
  <StrictMode>
    <AeroGuardProvider>
      <App />
    </AeroGuardProvider>
  </StrictMode>,
);
