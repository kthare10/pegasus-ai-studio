import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
  ILayoutRestorer
} from '@jupyterlab/application';
import {
  ICommandPalette,
  IFrame,
  MainAreaWidget,
  WidgetTracker
} from '@jupyterlab/apputils';
import { ILauncher } from '@jupyterlab/launcher';
import { LabIcon } from '@jupyterlab/ui-components';

// PegasusAI wing-plume mark (matches the studio chat logo).
const pegasusSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none">
<defs><linearGradient id="pg" x1="2" y1="22" x2="22" y2="2">
<stop offset="0%" stop-color="#0f2942"/><stop offset="55%" stop-color="#1e3a5f"/><stop offset="100%" stop-color="#0891b2"/></linearGradient></defs>
<circle cx="12" cy="12" r="12" fill="url(#pg)"/>
<path d="M5.4 17 Q11 13.6 16.6 11.1" stroke="#fff" stroke-width="1.7" stroke-linecap="round" fill="none"/>
<path d="M6 15.9 Q10.6 11.5 15.1 7.7" stroke="#cdeffb" stroke-width="1.6" stroke-linecap="round" fill="none"/>
<path d="M6.7 14.9 Q9.7 10.6 12.8 6.4" stroke="#7fe3f5" stroke-width="1.5" stroke-linecap="round" fill="none"/>
<path d="M17.9 3.7 C18.15 5.45 18.75 6.05 20.5 6.3 C18.75 6.55 18.15 7.15 17.9 8.9 C17.65 7.15 17.05 6.55 15.3 6.3 C17.05 6.05 17.65 5.45 17.9 3.7 Z" fill="#fff"/></svg>`;

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
    const tracker = new WidgetTracker<MainAreaWidget<IFrame>>({
      namespace: 'pegasusai-chat'
    });
    let widget: MainAreaWidget<IFrame> | null = null;

    const newWidget = (): MainAreaWidget<IFrame> => {
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
      iframe.title.label = 'PegasusAI Chat';
      iframe.title.icon = pegasusIcon;
      iframe.title.closable = true;
      const w = new MainAreaWidget({ content: iframe });
      w.id = 'pegasusai-chat';
      w.title.label = 'PegasusAI Chat';
      w.title.icon = pegasusIcon;
      w.title.closable = true;
      return w;
    };

    app.commands.addCommand(COMMAND, {
      label: 'PegasusAI Chat',
      caption: 'Open the PegasusAI workflow assistant',
      icon: pegasusIcon,
      execute: () => {
        if (!widget || widget.isDisposed) {
          widget = newWidget();
          widget.disposed.connect(() => {
            widget = null;
          });
        }
        if (!tracker.has(widget)) {
          void tracker.add(widget);
        }
        if (!widget.isAttached) {
          // Dock on the right as a side panel.
          app.shell.add(widget, 'right', { rank: 500 });
        }
        app.shell.activateById(widget.id);
      }
    });

    if (launcher) {
      launcher.add({ command: COMMAND, category: 'Other', rank: 1 });
    }
    if (palette) {
      palette.addItem({ command: COMMAND, category: 'PegasusAI' });
    }
    if (restorer) {
      void restorer.restore(tracker, {
        command: COMMAND,
        name: () => 'pegasusai-chat'
      });
    }
  }
};

export default plugin;
