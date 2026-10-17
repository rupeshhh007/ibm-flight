import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AeroGuardProvider } from "./hooks/useAeroGuard";
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
