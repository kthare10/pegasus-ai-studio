import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
  ILayoutRestorer
} from '@jupyterlab/application';
import { ICommandPalette, IFrame } from '@jupyterlab/apputils';
import { ILauncher } from '@jupyterlab/launcher';
import { LabIcon } from '@jupyterlab/ui-components';

// Monochrome chat glyph (currentColor) — JupyterLab sidebar icons are
// single-color line-art, and LabIcon runs svgstr through decodeURIComponent,
// which rejected the gradient/hex badge. A clean currentColor path is both
// the convention and safe to render. The colorful brand mark lives in the
// studio web UI (PegasusLogo); here a speech bubble + spark reads as "AI chat".
const pegasusSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16">
<path fill="currentColor" fill-rule="evenodd" clip-rule="evenodd" d="M4 2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 2-2zm8.6 4.2l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9.9-2.1z"/>
</svg>`;

const pegasusIcon = new LabIcon({
  name: 'pegasusai:logo',
  svgstr: pegasusSvg
});

const COMMAND = 'pegasusai:open-chat';

/**
 * Adds a "PegasusAI Chat" panel that embeds the studio chat (/chat) as an
 * iframe. Same-origin with JupyterLab, so the gateway session and the
 * studio's /api calls work without extra auth.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'jupyter-pegasusai-chat:plugin',
  autoStart: true,
  optional: [ILauncher, ICommandPalette, ILayoutRestorer],
  activate: (
    app: JupyterFrontEnd,
    launcher: ILauncher | null,
    palette: ICommandPalette | null,
    restorer: ILayoutRestorer | null
  ) => {
    let widget: IFrame | null = null;

    // Create the chat iframe and dock it in the right sidebar (so its icon is
    // always visible, like the file browser). Returns the existing one if live.
    const ensureWidget = (): IFrame => {
      if (widget && !widget.isDisposed) {
        return widget;
      }
      const iframe = new IFrame({
        sandbox: [
          'allow-scripts',
          'allow-same-origin',
          'allow-forms',
          'allow-popups',
          'allow-downloads'
        ]
      });
      // Absolute path -> resolves to https://<host>/chat (studio app),
      // same origin as /jupyter/, so cookies + /api work.
      iframe.url = '/chat';
      iframe.id = 'pegasusai-chat';
      iframe.title.label = 'PegasusAI Chat';
      iframe.title.icon = pegasusIcon;
      iframe.title.caption = 'PegasusAI workflow assistant';
      iframe.title.closable = false;
      iframe.disposed.connect(() => {
        widget = null;
      });
      widget = iframe;
      app.shell.add(iframe, 'right', { rank: 500 });
      return iframe;
    };

    app.commands.addCommand(COMMAND, {
      label: 'PegasusAI Chat',
      caption: 'Open the PegasusAI workflow assistant',
      icon: pegasusIcon,
      execute: () => {
        const w = ensureWidget();
        app.shell.activateById(w.id);
      }
    });

    if (launcher) {
      launcher.add({ command: COMMAND, category: 'Other', rank: 1 });
    }
    if (palette) {
      palette.addItem({ command: COMMAND, category: 'PegasusAI' });
    }

    // Dock the panel on startup so the right-sidebar icon is always present.
    void Promise.resolve(restorer ? app.restored : null).then(() => {
      ensureWidget();
    });
  }
};

export default plugin;
