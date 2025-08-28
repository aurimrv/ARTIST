"""
Templates package for the API Test Generator System.
"""

from .junit_template import JUnitTemplate
from .rest_assured_template import RestAssuredTemplate
from .maven_project_template import MavenProjectTemplate

__all__ = ['JUnitTemplate', 'RestAssuredTemplate', 'MavenProjectTemplate']

