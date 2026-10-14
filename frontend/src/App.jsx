import { useEffect, useState } from "react";
import Layout from "./components/Layout";
import { ToastProvider } from "./components/ui";
import Catalogue from "./pages/Catalogue";
import Desk from "./pages/Desk";
import Holds from "./pages/Holds";
import Insights from "./pages/Insights";
import Members from "./pages/Members";

const ROUTES = [
  {
    path: "catalogue",
    label: "Catalogue",
    icon: "📚",
    subtitle: "Every title in the collection, with live copy availability and holds",
    Page: Catalogue,
  },
  {
    path: "desk",
    label: "Circulation desk",
    icon: "🔁",
    subtitle: "Lend, return and renew books",
    Page: Desk,
  },
  {
    path: "holds",
    label: "Holds",
    icon: "⏳",
    subtitle: "Who is waiting for which book, in order",
    Page: Holds,
  },
  {
    path: "members",
    label: "Members",
    icon: "🪪",
    subtitle: "Library cards, borrowing limits and fines",
    Page: Members,
  },
  {
    path: "insights",
    label: "Insights",
    icon: "📈",
    subtitle: "How the collection is being used",
    Page: Insights,
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
