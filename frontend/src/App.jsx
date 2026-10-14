import { useEffect, useState } from "react";
import Layout from "./components/Layout";
import { ToastProvider } from "./components/ui";
import Catalogue from "./pages/Catalogue";
import Desk from "./pages/Desk";

const ROUTES = [
  {
    path: "catalogue",
    label: "Catalogue",
    icon: "📚",
    subtitle: "Every title in the collection and how many copies are on the shelf",
    Page: Catalogue,
  },
  {
    path: "desk",
    label: "Circulation desk",
    icon: "🔁",
    subtitle: "Lend, return and renew books",
    Page: Desk,
  },
];

const currentPath = () => window.location.hash.replace(/^#\/?/, "").split("?")[0];

export default function App() {
  const [path, setPath] = useState(currentPath);

  useEffect(() => {
    const onChange = () => setPath(currentPath());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const route = ROUTES.find((r) => r.path === path) ?? ROUTES[0];
  const { Page } = route;

  return (
    <ToastProvider>
      <Layout routes={ROUTES} current={route.path}>
        <Page />
      </Layout>
    </ToastProvider>
  );
}
