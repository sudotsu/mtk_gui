"""Plugin discovery and loading."""
import importlib.util
import inspect
import logging
import os
import sys

from mtk_gui.plugins.base_plugin import MtkPlugin, PluginContext

logger = logging.getLogger(__name__)


def discover_plugins(search_dirs: list) -> list:
    """
    Discover plugin instances from Python files in the specified directories.
    
    Parameters:
        search_dirs (list): Directories to scan for plugin files.
    
    Returns:
        list: Instances of concrete `MtkPlugin` subclasses found in the directories.
    """
    plugins = []

    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue

        for filename in os.listdir(directory):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            filepath = os.path.join(directory, filename)
            module_name = f"mtk_plugin_{filename[:-3]}"

            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, MtkPlugin) and obj is not MtkPlugin:
                        plugins.append(obj())
                        logger.info(f"Discovered plugin: {obj.name} v{obj.version}")

            except Exception as e:
                logger.error(f"Failed to load plugin {filename}: {e}")

    return plugins


def load_plugins(app, search_dirs: list) -> list:
    """
    Discover and register plugins with the application.
    
    Parameters:
    	search_dirs (list): Directories to search for plugin files.
    
    Returns:
    	list: Successfully registered plugin instances.
    """
    plugins = discover_plugins(search_dirs)
    ctx = PluginContext(app)

    loaded = []
    for plugin in plugins:
        try:
            plugin.register(ctx)
            loaded.append(plugin)
            logger.info(f"Registered plugin: {plugin.name}")
        except Exception as e:
            logger.error(f"Failed to register plugin {plugin.name}: {e}")

    return loaded
