from setuptools import find_packages, setup

setup(
    name="opencode-extension",
    version="0.1.0",
    packages=find_packages(),
    package_data={"opencode_extension": ["static/*"]},
    entry_points={
        "jupyter_serverproxy_servers": [
            "opencode = opencode_extension:setup_opencode_proxy",
        ],
    },
    install_requires=["jupyter-server-proxy>=4.4.0", "jupyter-server"],
)
