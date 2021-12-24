## github_metadata

- Gathers project/repository metdata from GitHub API and add it to YAML data.
- Checks the last `updated_at` date of GitHub projects against a "freshness" threshold in days.

A Github access token (without privileges) must be defined in the `GITHUB_TOKEN` environment variable.

```bash
GITHUB_TOKEN=AAAbbbCCCdd... hecat process --processors github_metadata --source-directory awesome-selfhosted-data --options
```

On Github Actions a token is created automatically for each job. To make it available in the environment use the following workflow configuration:

```yaml
env:
  GITHUB_TOKEN: ${{secrets.GITHUB_TOKEN}}

jobs:
...
```