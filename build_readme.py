from python_graphql_client import GraphqlClient
import requests
import csv
from rdflib import Graph
import json
import pathlib
import re
import os


CONTRIBUTIONS_COUNT=12

TOKEN = os.environ.get("GITHUB_TOKEN", "")

root = pathlib.Path(__file__).parent.resolve()
client = GraphqlClient(endpoint="https://api.github.com/graphql")


def replace_chunk(content, marker, chunk, inline=False):
    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = "<!-- {} starts -->{}<!-- {} ends -->".format(marker, chunk, marker)
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
        "AFTER", '"{}"'.format(after_cursor) if after_cursor else "null"
    )


def fetch_releases(oauth_token):
    repos = []
    releases = []
    repo_names = set()
    has_next_page = True
    after_cursor = None

    while has_next_page:
        data = client.execute(
            query=make_query(after_cursor),
            headers={"Authorization": "Bearer {}".format(oauth_token)},
        )
        print()
        print(json.dumps(data, indent=4))
        print()
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


def fetch_contributions(oauth_token):
    graphql_get_contributions = """
    query {
        viewer {
            repositoriesContributedTo(first: 100, contributionTypes: [COMMIT], orderBy:{field: STARGAZERS, direction: DESC}) {
                totalCount
                nodes {
                    nameWithOwner
                    url
                    description
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
    data = client.execute(
        query=graphql_get_contributions,
        headers={"Authorization": "Bearer {}".format(oauth_token)},
    )
    for repo in data["data"]["viewer"]["repositoriesContributedTo"]["nodes"]:
        # Do not take MaastrichtU-IDS repos
        if repo['owner']['id'] != 'MDEyOk9yZ2FuaXphdGlvbjM2MjYyNTI2':
            contributions.append(
                {
                    "nameWithOwner": repo["nameWithOwner"],
                    "url": repo["url"],
                    "description": repo["description"]
                }
            )
    return contributions


if __name__ == "__main__":
    readme = root / "README.md"

    readme_contents = readme.open().read()

    ## Get Contributions to other repositories
    contributions = fetch_contributions(TOKEN)
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
    releases = fetch_releases(TOKEN)
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


    ### Get all my nanopublications (test)

    # curl -X GET "http://grlc.nanopubs.lod.labs.vu.nl/api/local/local/find_signed_nanopubs?pubkey=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCR9fz0fKCdWOWC%2BpxhkQhEM%2FppbdIYe5TLSdj%2BlJzSlv9mYBaPgrzVezSwwbmhlHBPDZa4%2FvHycU315BdmUGq%2BpXllp9%2BrWFfrb%2BkBJwhZjpG6BeyyXBsRFz4jmQVxl%2FZYHilQTh%2FXalYzKkEAyTiEMPee4Kz61PaWOKH24CsnOQIDAQAB" -H  "accept: text/csv"
    # nanopubs_request = requests.get('http://grlc.nanopubs.lod.labs.vu.nl/api/local/local/find_signed_nanopubs?pubkey=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCR9fz0fKCdWOWC%2BpxhkQhEM%2FppbdIYe5TLSdj%2BlJzSlv9mYBaPgrzVezSwwbmhlHBPDZa4%2FvHycU315BdmUGq%2BpXllp9%2BrWFfrb%2BkBJwhZjpG6BeyyXBsRFz4jmQVxl%2FZYHilQTh%2FXalYzKkEAyTiEMPee4Kz61PaWOKH24CsnOQIDAQAB',
    #         headers={"accept": "text/csv"})

    # print(nanopubs_request.content)
    # nanopubs_csv = csv.reader(nanopubs_request, delimiter=',')
    # graph = Graph()
    # line_count = 0
    # for row in nanopubs_csv:
    #     if line_count == 0:
    #         print(f'Column names are {", ".join(row)}')
    #         line_count += 1
    #     else:
    #         print('Getting nanopub: ' + row[0])
    #         nanopubs_request = requests.get(row[0], headers={"accept": "text/x-nquads"})
    #         nanopubs_request.content
    #         graph.parse(nanopubs_request.content, format="nquads")
    #         print(len(graph))
    #         # nanopubs_request = requests.get('http://purl.org/np/RAc99KPv1qM3J6tyIpYRY3yh1LR5u15FwByJ78-k4Ix6E', headers={"accept": "text/x-nquads"})
    #         line_count += 1

    # graph.parse('http://purl.org/np/RAc99KPv1qM3J6tyIpYRY3yh1LR5u15FwByJ78-k4Ix6E', format='text/x-nquads')
    # graph.parse(row[0], format='text/x-nquads')

    # import pprint
    # for stmt in graph:
    #     pprint.pprint(stmt)

    ## Get a nanopub as nquads:
    # curl -L -X GET "http://purl.org/np/RAc99KPv1qM3J6tyIpYRY3yh1LR5u15FwByJ78-k4Ix6E"  -H "accept: text/x-nquads"

    # tils = fetch_tils()
    # tils_md = "\n".join(
    #     [
    #         "* [{title}]({url}) - {created_at}".format(
    #             title=til["title"],
    #             url=til["url"],
    #             created_at=til["created_utc"].split("T")[0],
    #         )
    #         for til in tils
    #     ]
    # )
    # rewritten = replace_chunk(rewritten, "tils", tils_md)

