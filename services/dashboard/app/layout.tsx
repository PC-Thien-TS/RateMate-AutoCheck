export const metadata = {
  title: 'TaaS Dashboard',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: 'system-ui, sans-serif', margin: 20 }}>
        <h1>TaaS Dashboard</h1>
        <nav style={{ marginBottom: 16 }}>
          <a href="/">Home</a>
          <span> · </span>
          <a href="/run">Run Test</a>
          <span> · </span>
          <a href="/run-mobile">Run Mobile Analyze</a>
          <span> · </span>
          <a href="/admin/keys">Admin Keys</a>
        </nav>
        {/* Queue stats (auto-refresh) */}
        <StatsBar />
        {children}
      </body>
    </html>
  );
}
import StatsBar from "../components/StatsBar";
