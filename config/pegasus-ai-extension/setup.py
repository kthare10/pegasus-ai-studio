from setuptools import find_packages, setup

setup(
    name="pegasus-ai-extension",
    version="0.1.0",
    packages=find_packages(),
    package_data={"pegasus_ai_extension": ["static/*"]},
    entry_points={
        "jupyter_serverproxy_servers": [
            "pegasus-ai = pegasus_ai_extension:setup_pegasus_ai_proxy",
        ],
    },
    install_requires=["jupyter-server-proxy>=4.4.0", "jupyter-server", "httpx"],
)
