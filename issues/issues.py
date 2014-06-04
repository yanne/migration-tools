import argparse
import getpass
import csv
from urllib2 import urlopen

from bs4 import BeautifulSoup
from github3 import login


GOOGLE_CODE_ISSUES = (
    'http://code.google.com/p/{project}/issues/csv?start={start}&num={num}'
    '&colspec=ID%20Status%20Type%20Priority%20Target%20Summary&can=1')
ISSUE_URL = 'http://code.google.com/p/{project}/issues/detail?id={id}'
ISSUE_BODY = u"""{description}

This issue was originally opened at <a href="{url}">Google Code</a> on {date}.
"""
COMMENT = u"""Original comment by `{user}` on {date}.

{content}
"""
CLOSED_STATES = ['wontfix', 'done', 'invalid']


class IssueTransfomer(object):

    def __init__(self, project, id, status, type_, priority, target, summary):
        self.summary = summary
        self.open = status.lower() not in CLOSED_STATES
        self.labels = ['Type-' + type_, 'Priority-' + priority]
        self.target = target
        self.body, self.comments = self._get_issue_details(project, id)

    def _get_issue_details(self, project, id):
        url = ISSUE_URL.format(project=project, id=id)
        soup = BeautifulSoup(urlopen(url).read())
        return self._format_body(soup, url), self._format_comments(soup)

    def _format_body(self, details, url):
        description = details.select('div.issuedescription pre')[0].string
        date = details.select('div.issuedescription .date')[0].string
        return ISSUE_BODY.format(description=description, date=date, url=url)

    def _format_comments(self, details):
        for comment in details.select('div.issuecomment'):
            content = '\n'.join(
                [unicode(part) for part in comment.find(name='pre').strings])
            user = comment.find(class_='userlink').string
            date = comment.find(class_='date').string.strip()
            yield COMMENT.format(content=content, user=user, date=date)

    def __str__(self):
        return 'Title: "{0}" Open: {1} Target: {2} Labels: {3}'.format(
            self.summary, self.open, self.target, self.labels)


def main(source_project, target_project, github_username, issue_limit):
    gh, repo = access_github_repo(target_project, github_username)
    existing_issues = [i.title for i in repo.iter_issues()]
    for issue in get_google_code_issues(source_project, issue_limit):
        debug('Processing issue:\n{issue}'.format(issue=issue))
        milestone = get_milestone(repo, issue)
        if issue.summary in existing_issues:
            debug('Skipping already processed issue')
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


def get_google_code_issues(project, issue_limit):
    limit_issues = issue_limit > 0
    start = 0
    issues = []
    num = 100
    while True:
        if limit_issues:
            if issue_limit <= 0:
                return issues
            num = min(issue_limit, 100)
            issue_limit -= 100
        url = GOOGLE_CODE_ISSUES.format(project=project, start=start, num=num)
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
                issues.append(IssueTransfomer(project, *row[:6]))
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
    if not issue.open:
        github_issue.close()
    debug('Created issue {url}'.format(url=github_issue.html_url))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Migrate issues from Google Code to GitHub')
    parser.add_argument('source_project')
    parser.add_argument('target_project')
    parser.add_argument('github_username')
    parser.add_argument('-n', dest='limit', default=0)
    args = parser.parse_args()

    main(args.source_project, args.target_project, args.github_username,
         int(args.limit))
