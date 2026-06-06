"""
Project Provider - Reads project status from a local JSON file.
"""

import json
import os


class ProjectProvider:
    """
    Reads project progress data from a local JSON file.

    The project status file is maintained manually by the user
    and contains information about current project progress,
    milestones, and upcoming tasks.
    """

    def __init__(self, status_file="project_status.json"):
        self.status_file = status_file

    def get_status(self):
        """
        Read and return project status data.

        Returns:
            dict: Project status information
        """
        if not os.path.exists(self.status_file):
            return {
                "project_name": "No Project",
                "status": "No project status file found",
                "progress": 0,
            }

        try:
            with open(self.status_file, "r") as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"[ProjectProvider] Error reading status: {e}")
            return {
                "project_name": "Error",
                "status": f"Could not read project file: {e}",
                "progress": 0,
            }

    def get_summary_text(self):
        """
        Get a spoken summary of the project status.

        Returns:
            str: Natural language summary
        """
        data = self.get_status()

        name = data.get("project_name", "Unknown project")
        progress = data.get("overall_progress", 0)
        status = data.get("status", "unknown status")
        next_steps = data.get("next_steps", [])

        summary = f"The current project is {name}, which is {status} at {progress}% progress."

        if next_steps:
            summary += f" Next steps include: {', '.join(next_steps[:3])}."

        return summary
