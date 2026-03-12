from setuptools import find_packages, setup

setup(
    name="claude-code-extension",
    version="0.1.0",
    packages=find_packages(),
    package_data={"claude_code_extension": ["static/*"]},
    entry_points={
        "jupyter_serverproxy_servers": [
            "claude-code = claude_code_extension:setup_claude_code_proxy",
        ],
    },
    install_requires=["jupyter-server-proxy>=4.4.0", "jupyter-server"],
)
