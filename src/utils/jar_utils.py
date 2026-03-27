"""
Utility for inspecting JAR files to extract class and package information.
"""

import zipfile
from pathlib import Path
from typing import List, Set, Dict
import logging

logger = logging.getLogger(__name__)

def list_jar_classes(jar_path: Path) -> List[str]:
    """
    List all fully qualified class names in a JAR file.
    
    Example: 'eu/fayder/restcountries/v1/rest/CountryService.class' 
             becomes 'eu.fayder.restcountries.v1.rest.CountryService'
    """
    classes = []
    if not jar_path or not jar_path.exists():
        return classes

    try:
        with zipfile.ZipFile(jar_path, 'r') as jar:
            for name in jar.namelist():
                if name.endswith('.class') and not name.startswith('META-INF/'):
                    # Convert path to fully qualified class name
                    class_name = name[:-6].replace('/', '.')
                    classes.append(class_name)
    except Exception as e:
        logger.error(f"Failed to list classes in JAR {jar_path}: {e}")
        
    return classes

def get_jar_packages(jar_path: Path) -> Set[str]:
    """Get all unique package names present in the JAR."""
    classes = list_jar_classes(jar_path)
    packages = set()
    for cls in classes:
        if '.' in cls:
            packages.add(cls.rsplit('.', 1)[0])
    return packages

def find_class_in_jar(jar_path: Path, simple_name: str) -> List[str]:
    """
    Find all fully qualified names in the JAR that match a simple class name.
    
    Args:
        jar_path: Path to the JAR file.
        simple_name: The simple class name to find (e.g., 'CountryService').
        
    Returns:
        List of fully qualified names (e.g., ['eu.fayder.restcountries.v1.rest.CountryService']).
    """
    classes = list_jar_classes(jar_path)
    return [cls for cls in classes if cls.endswith('.' + simple_name) or cls == simple_name]

def get_jar_inventory(jar_path: Path) -> Dict[str, List[str]]:
    """
    Create an inventory of the JAR: mapping simple class names to their full names.
    
    Returns:
        Dict where key is simple name (e.g. 'CountryService') 
        and value is list of full names.
    """
    inventory = {}
    classes = list_jar_classes(jar_path)
    for full_name in classes:
        simple_name = full_name.split('.')[-1]
        inventory.setdefault(simple_name, []).append(full_name)
    return inventory
