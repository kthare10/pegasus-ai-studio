# PegasusAI Studio: per-user AI tools (claude, codex, opencode, ...) are
# npm-installed under ~/.npm-global by the studio — put them on PATH for
# every login shell (SSH, JupyterLab terminals run bash -l).
export NPM_CONFIG_PREFIX="$HOME/.npm-global"
case ":$PATH:" in
    *":$HOME/.npm-global/bin:"*) ;;
    *) export PATH="$HOME/.npm-global/bin:$PATH" ;;
esac
