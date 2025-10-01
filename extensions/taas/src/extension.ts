import * as vscode from 'vscode';

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || 'http://localhost:8088';

export function activate(context: vscode.ExtensionContext) {
  const generateTests = vscode.commands.registerCommand('taas.generateTests', async () => {
    const editor = vscode.window.activeTextEditor;
    const spec = editor ? editor.document.getText() : '';
    try {
      const response = await fetch(`${ORCHESTRATOR_URL}/generate-tests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_root: vscode.workspace.rootPath ?? '', target: 'web', spec_md: spec })
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Failed with status ${response.status}`);
      }
      const data = (await response.json()) as { patch: string; summary?: string };
      const panel = vscode.window.createOutputChannel('TaaS');
      panel.show(true);
      panel.appendLine('--- Generated Patch (preview) ---');
      panel.appendLine(data.patch);
      if (data.summary) {
        panel.appendLine('\nSummary:');
        panel.appendLine(data.summary);
      }
      vscode.window.showInformationMessage('TaaS: Patch generated. Review the output channel for details.');
    } catch (error) {
      vscode.window.showErrorMessage(`TaaS generate failed: ${(error as Error).message}`);
    }
  });

  context.subscriptions.push(generateTests);
}

export function deactivate() {
  // no-op
}

