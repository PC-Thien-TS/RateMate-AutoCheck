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
        </nav>
        {children}
      </body>
    </html>
  );
}
