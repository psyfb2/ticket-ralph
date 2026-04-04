```json
{
  "summary": "string — one-paragraph summary of the user-requirements/story and its goal",
  "requirements": ["string — each element is a clear and unambiguous user requirement"],
  "highLevelDesign": "string — high-level design and architecture",
  "tasks": [
    {
      "taskNumber": "int — incrementing starting from 1",
      "title": "string — short task title",
      "description": "string — what to do, key files to touch, acceptance criteria",
      "dependsOn": ["int — task numbers this task depends on"],
      "done": false
    }
  ],
  "topBranch": "string - top level branch for this PRD. All tasks branch from and merge to this branch"
}
```
