import { Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import Accounts from "./pages/Accounts";
import Budget from "./pages/Budget";
import Business from "./pages/Business";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";
import Transactions from "./pages/Transactions";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/business" element={<Business />} />
        <Route path="/budget" element={<Budget />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}
