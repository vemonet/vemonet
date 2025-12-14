import os
import pathlib
import re

import httpx


CONTRIBUTIONS_COUNT=10

root = pathlib.Path(__file__).parent.resolve()

class GraphqlClient:
    def __init__(self, endpoint: str) -> None:
        self.client = httpx.Client(timeout=60)
        self.oauth_token = os.environ.get("GITHUB_TOKEN")
        if not self.oauth_token:
            raise ValueError("GITHUB_TOKEN environment variable is not set")
        self.endpoint = endpoint

    def execute(self, query: str, variables=None):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        response = self.client.post(
            self.endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {self.oauth_token}"},
        )
        response.raise_for_status()
        return response.json()

client = GraphqlClient(endpoint="https://api.github.com/graphql")



def fetch_contributions():
    graphql_get_contributions = """
    query($cursor: String) {
        viewer {
            repositoriesContributedTo(first: 100, contributionTypes: [COMMIT], after: $cursor) {
                totalCount
                nodes {
                    nameWithOwner
                    url
                    description
                    stargazerCount
                    owner { id }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }
    """
    contributions = []
    has_next_page = True
    after_cursor = None

    while has_next_page:
        variables = {"cursor": after_cursor}
        data = client.execute(
            query=graphql_get_contributions,
            variables=variables,
        )

        page_info = data["data"]["viewer"]["repositoriesContributedTo"]["pageInfo"]
        for repo in data["data"]["viewer"]["repositoriesContributedTo"]["nodes"]:
            # print(repo)
            contributions.append(
                {
                    "nameWithOwner": repo["nameWithOwner"],
                    "url": repo["url"],
                    "description": repo["description"],
                    "stargazerCount": repo.get("stargazerCount", 0)
                }
            )
        print(f"Fetched {len(contributions)} contributions so far...")
        has_next_page = page_info["hasNextPage"]
        after_cursor = page_info["endCursor"]

    # Sort contributions by star count after all are fetched
    contributions.sort(key=lambda r: r.get("stargazerCount", 0), reverse=True)
    # print(json.dumps(contributions, indent=2))
    return contributions



def replace_chunk(content, marker, chunk, inline=False):
    r = re.compile(
        rf"<!\-\- {marker} starts \-\->.*<!\-\- {marker} ends \-\->",
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = f"<!-- {marker} starts -->{chunk}<!-- {marker} ends -->"
    return r.sub(chunk, content)


def make_query(after_cursor=None):
    return """
query {
  viewer {
    repositories(first: 100, privacy: PUBLIC, after:AFTER) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        description
        url
        releases(last:1) {
          totalCount
          nodes {
            name
            publishedAt
            url
          }
        }
      }
    }
  }
}
""".replace(
        "AFTER", f'"{after_cursor}"' if after_cursor else "null"
    )


def fetch_releases():
    repos = []
    releases = []
    repo_names = set()
    has_next_page = True
    after_cursor = None

    while has_next_page:
        data = client.execute(query=make_query(after_cursor))
        # print()
        # print(json.dumps(data, indent=4))
        # print()
        for repo in data["data"]["viewer"]["repositories"]["nodes"]:
            if repo["releases"]["totalCount"] and repo["name"] not in repo_names:
                repos.append(repo)
                repo_names.add(repo["name"])
                releases.append(
                    {
                        "repo": repo["name"],
                        "repo_url": repo["url"],
                        "description": repo["description"],
                        "release": repo["releases"]["nodes"][0]["name"]
                        .replace(repo["name"], "")
                        .strip(),
                        "published_at": repo["releases"]["nodes"][0][
                            "publishedAt"
                        ].split("T")[0],
                        "url": repo["releases"]["nodes"][0]["url"],
                    }
                )
        has_next_page = data["data"]["viewer"]["repositories"]["pageInfo"][
            "hasNextPage"
        ]
        after_cursor = data["data"]["viewer"]["repositories"]["pageInfo"]["endCursor"]
    return releases


if __name__ == "__main__":
    readme = root / "README.md"

    readme_contents = readme.open().read()

    ## Get Contributions to other repositories
    contributions = fetch_contributions()
    # contributions.sort(key=lambda r: r["published_at"], reverse=True)
    contributions_md = "\n".join(
        [
            (
                "* [{nameWithOwner}]({url}) - {description}"
            ).format(**contribution)
            for contribution in contributions[:CONTRIBUTIONS_COUNT]
        ]
    )
    rewritten = replace_chunk(readme_contents, "contributions", contributions_md)

    ## Save updated readme
    readme.open("w").write(rewritten)


    ## Get releases to put in releases.md
    project_releases = root / "releases.md"
    releases = fetch_releases()
    releases.sort(key=lambda r: r["published_at"], reverse=True)

    project_releases_md = "\n".join(
        [
            (
                "* **[{repo}]({repo_url})**: [{release}]({url}) - {published_at}\n"
                "<br>{description}"
            ).format(**release)
            for release in releases
        ]
    )
    project_releases_content = project_releases.open().read()
    project_releases_content = replace_chunk(
        project_releases_content, "recent_releases", project_releases_md
    )
    project_releases_content = replace_chunk(
        project_releases_content, "release_count", str(len(releases)), inline=True
    )
    project_releases.open("w").write(project_releases_content)

    ## Currently not putting releases in the main README anymore
    # readme_releases_md = "\n".join(
    #     [
    #         "* [{repo} {release}]({url}) - {published_at}".format(**release)
    #         for release in releases[:8]
    #     ]
    # )
    # rewritten = replace_chunk(readme_contents, "recent_releases", readme_releases_md)
