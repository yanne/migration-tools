import argparse
import getpass
import sys
import csv
from urllib2 import urlopen
from string import Template

from bs4 import BeautifulSoup
from github3 import login


GOOGLE_CODE_ISSUES = Template(
    'http://code.google.com/p/${project}/issues/csv?'
    'sort=priority+type&colspec=ID%20Type%20Priority%20Target%20Summary&can=2')
ISSUE_BODY = u"""{description}

This issue was originally reported to <a href="{url}">Google Code</a> on {date}.
"""
COMMENT = u"""Original comment by `{user}` on {date}.

{content}
"""


class IssueTransfomer(object):

    def __init__(self, project, id, type_, priority, target, summary):
        self.summary = summary
        self.labels = ['Type-' + type_, 'Priority-' + priority]
        self.milestone = 1 if target else 0
        self.body, self.comments = self._get_issue_details(project, id)

    def _get_issue_details(self, project, id):
        url = 'http://code.google.com/p/{project}/issues/detail?id={id}'.format(
            project=project, id=id)
        soup = BeautifulSoup(urlopen(url).read())
        return self._format_body(soup, url), self._format_comments(soup)

    def _format_body(self, details, url):
        description = details.select('div.issuedescription pre')[0].string
        date = details.select('div.issuedescription .date')[0].string
        return ISSUE_BODY.format(description=description, date=date, url=url)

    def _format_comments(self, details):
        for raw_comment in details.select('div.issuecomment'):
            content = '\n'.join(
                [unicode(part) for part in raw_comment.find(name='pre').strings])
            user = raw_comment.find(class_='userlink').string
            date = raw_comment.find(class_='date').string
            yield COMMENT.format(content=content, user=user, date=date)


def main(source_project, target_project, github_username):
    repo = access_github_repo(target_project, github_username)
    for issue in get_google_code_issues(source_project):
        debug('Processing issue {title}'.format(title=issue.summary))
        insert_issue(repo, issue)
        break


def access_github_repo(target_project, github_username):
    github_password = getpass.getpass(
        'Github password for {user}: '.format(user=github_username))
    gh = login(github_username, password=github_password)
    repo_owner, repo_name = target_project.split('/')
    return gh.repository(repo_owner, repo_name)


def get_google_code_issues(project):
    url = GOOGLE_CODE_ISSUES.substitute({'project': project})
    debug('Fetching issues from {url}'.format(url=url))
    reader = csv.reader(urlopen(url))
    for row in reader:
        if reader.line_num == 1 or not row:
            continue
        yield IssueTransfomer(project, *row[:5])


def debug(msg):
    print msg


def insert_issue(repo, issue):
    github_issue = repo.create_issue(
        issue.summary, issue.body, labels=issue.labels,
        milestone=issue.milestone)
    for comment in issue.comments:
        github_issue.create_comment(comment)
    debug('Created issue {url}'.format(url=github_issue.html_url))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate issues from Google Code to GitHub')
    parser.add_argument('source_project')
    parser.add_argument('target_project')
    parser.add_argument('github_username')
    args = parser.parse_args()

    main(args.source_project, args.target_project, args.github_username)

