import argparse
import getpass
import sys
import csv
from urllib2 import urlopen
from string import Template

from bs4 import BeautifulSoup
from github3 import login


GOOGLE_CODE_ISSUES = (
    'http://code.google.com/p/{project}/issues/csv?'
    'sort=priority+type&colspec=ID%20Type%20Priority%20Target%20Summary&start={start}&can=2')
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
        self.target = target
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
            date = raw_comment.find(class_='date').string.strip()
            yield COMMENT.format(content=content, user=user, date=date)


def main(source_project, target_project, github_username):
    gh, repo = access_github_repo(target_project, github_username)
    existing_issues = [i.title for i in repo.iter_issues(state='open')]
    for issue in get_google_code_issues(source_project):
        debug('Processing issue {title}'.format(title=issue.summary))
        milestone = get_milestone(repo, issue)
        if issue.summary in existing_issues:
            debug('Skipping already processed issue "{title}"'.format(
                  title=issue.summary))
            continue
        insert_issue(repo, issue, milestone)
        if api_call_limit_reached(gh):
            break



def access_github_repo(target_project, github_username):
    github_password = getpass.getpass(
        'Github password for {user}: '.format(user=github_username))
    gh = login(github_username, password=github_password)
    repo_owner, repo_name = target_project.split('/')
    return gh, gh.repository(repo_owner, repo_name)


def get_google_code_issues(project):
    start = 0
    issues = []
    while True:
        url = GOOGLE_CODE_ISSUES.format(project=project, start=start)
        debug('Fetching issues from {url}'.format(url=url))
        reader = csv.reader(urlopen(url))
        paginated = False
        for row in reader:
            if reader.line_num == 1 or not row:
                continue
            if 'truncated' in row[0]:
                start += 100
                paginated = True
            else:
                issues.append(IssueTransfomer(project, *row[:5]))
        if not paginated:
            debug('Read {num} issues from Google Code'.format(num=len(issues)))
            return issues



def get_milestone(repo, issue):
    if not issue.target:
        return None
    existing_milestones = list(repo.iter_milestones())
    milestone = [m for m in existing_milestones if m.title == issue.target]
    if milestone:
        return milestone[0].number
    return repo.create_milestone(issue.target).number


def api_call_limit_reached(gh):
    remaining = gh.ratelimit_remaining
    debug('Remaining API calls: {rem}'.format(rem=remaining))
    if remaining < 50:
        debug('API calls consumed, wait for an hour')
        return True
    return False


def debug(msg):
    print msg


def insert_issue(repo, issue, milestone):
    github_issue = repo.create_issue(
        issue.summary, issue.body, labels=issue.labels,
        milestone=milestone)
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

