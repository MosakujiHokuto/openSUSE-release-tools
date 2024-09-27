#!/usr/bin/python3

import PackageLookup, ReviewChoices, CommentFromLogHandler, CommandLine from ReviewBotOBS
import ReviewBotOBS from ReviewBotOBS

class ReviewBot(object):
    """
    A generic obs request reviewer
    Inherit from this class and implement check functions for each action type:

    def check_action_<type>(self, req, action):
        return (None|True|False)
    """

    DEFAULT_REVIEW_MESSAGES = {'accepted': 'ok', 'declined': 'review failed'}
    REVIEW_CHOICES: Tuple[ReviewChoices, ...] = (
        ReviewChoices.NORMAL, ReviewChoices.NO, ReviewChoices.ACCEPT,
        ReviewChoices.ACCEPT_ONPASS, ReviewChoices.FALLBACK_ONFAIL, ReviewChoices.FALLBACK_ALWAYS
    )

    COMMENT_MARKER_REGEX = re.compile(r'<!-- (?P<bot>[^ ]+) state=(?P<state>[^ ]+)(?: result=(?P<result>[^ ]+))? -->')

    @attribute
    def config_defaults(self):
        return self.impl.config_defaults

    def __init__(self, *args, **kwargs):
        self.impl = ReviewBotOBS(*args, **kwargs)

    def load_config(self, filename=None):
        return self.impl.load_config(filename)

    def has_staging(self, project):
        return self.impl.has_staging(project)

    def staging_api(self, project):
        return self.impl.staging_api(project)

    @property
    def review_mode(self) -> ReviewChoices:
        return self.impl.review_mode

    @review_mode.setter
    def review_mode(self, value: Union[ReviewChoices, str]) -> None:
        self.impl.review_mode = value

    def set_request_ids(self, ids):
        self.impl.set_request_ids(ids)

    # function called before requests are reviewed
    def prepare_review(self):
        return self.impl.prepare_review(self)

    def check_requests(self):
        return self.impl.check_requests(self)

    def request_override_check_users(self, project: str) -> List[str]:
        return self.impl.request_override_check_users(project)

    def request_override_check(self, force: bool = False) -> Optional[bool]:
        return self.impl.request_override_check(self, force)

    def request_commands(self, command: str, who_allowed=None, request=None, action=None,
                         include_description=True) -> Generator[Tuple[List[str], Optional[str]], None, None]:
        return self.impl.request_commands(command, who_allowed, request, action, include_description)

    # allow_duplicate=True should only be used if it makes sense to force a
    # re-review in a scenario where the bot adding the review will rerun.
    # Normally a declined review will automatically be reopened along with the
    # request and any other bot reviews already added will not be touched unless
    # the issuing bot is rerun which does not fit normal workflow.
    def add_review(self, req, by_group=None, by_user=None, by_project=None, by_package=None,
                   msg=None, allow_duplicate=False):
        return self.impl.add_review(req, by_group, by_user, by_project, by_package, msg, allow_duplicate)

    def devel_project_review_add(self, request, project, package, message='adding devel project review'):
        return self.impl.devel_project_review_add(request, project, package, message)

    def devel_project_review_ensure(self, request, project, package, message='submitter not devel maintainer'):
        return self.impl.devel_project_review_ensure(request, project, package, message)

    def devel_project_review_needed(self, request, project, package):
        return self.impl.devel_project_review_needed(request, project, package)

    def check_one_request(self, req: osc.core.Request):
        return self.impl.check_one_request(req)

    def action_method(self, action: osc.core.Action):
        return self.impl.action_method(action)

    def review_message_key(self, result):
        return self.impl.review_message_key(result)

    def check_action_maintenance_incident(self, req, a):
        return self.impl.check_action_maintenance_incident(self, req, a)

    def check_action_maintenance_release(self, req: osc.core.Request, a: osc.core.Action):
        return self.impl.check_action_maintenance_release(req)

    def check_action_submit(self, req: osc.core.Request, a: osc.core.Action):
        return self.impl.check_action_submit(req)

    def check_action__default(self, req, a):
        return self.impl.check_action__default(req, a)

    def check_source_submission(self, src_project: str, src_package: str, src_rev: str, target_project: str, target_package: str) -> None:
        return self.impl.check_source_submission(src_project, src_package, src_rev, target_project, target_package)

    @staticmethod
    def _get_sourceinfo(apiurl, project, package, rev=None):
        # XXX: dispatch based on impl type
        return ReviewBotOBS._get_sourceinfo(apiurl, project, package, rev)

    def get_originproject(self, project, package, rev=None):
        return self.impl.get_originproject(project, package, rev)

    def get_sourceinfo(self, project, package, rev=None):
        return self.impl.get_sourceinfo(project, package, rev)

    def can_accept_review(self, request_id):
        return self.impl.can_accept_review(request_id)

    def set_request_ids_search_review(self):
        return self.impl.set_request_ids_search_review()

    # also used by openqabot
    def ids_project(self, project, typename):
        return self.impl.ids_project(project, typename)

    def set_request_ids_project(self, project, typename):
        return self.impl.set_request_ids_project(project, typename)

    def comment_handler_add(self, level=logging.INFO):
        return self.impl.comment_handler_add(level)

    def comment_handler_remove(self):
        return self.impl.comment_handler_remove()

    def comment_handler_lines_deduplicate(self):
        return self.impl.comment_handler_lines_deduplicate()

    def comment_write(self, state='done', result=None, project=None, package=None,
                      request=None, message=None, identical=False, only_replace=False,
                      info_extra=None, info_extra_identical=True, bot_name_suffix=None):
        return self.impl.comment_write(
            state, result, project, package, request, message, identical, only_replace,
            info_extra, info_extra_identical, bot_name_suffix)

    def request_age_wait(
            self,
            age_min: Optional[Union[str, int, float]] = None,
            request=None,
            target_project: Optional[str] = None
    ) -> bool:
        return self.impl.request_age_wait


class CommandLineInterface(cmdln.Cmdln):
    def __init__(self, *args, **kwargs):
        cmdln.Cmdln.__init__(self, args, kwargs)
        Cache.init()
        self.clazz = ReviewBot

    def get_optparser(self):
        parser = cmdln.Cmdln.get_optparser(self)
        parser.add_option("--apiurl", '-A', metavar="URL", help="api url")
        parser.add_option("--user", metavar="USER", help="reviewer user name")
        parser.add_option("--group", metavar="GROUP", help="reviewer group name")
        parser.add_option("--dry", action="store_true", help="dry run")
        parser.add_option("--debug", action="store_true", help="debug output")
        parser.add_option("--osc-debug", action="store_true", help="osc debug output")
        parser.add_option("--verbose", action="store_true", help="verbose")
        parser.add_option("--review-mode", dest='review_mode', choices=[c.value for c in ReviewBot.REVIEW_CHOICES], help="review behavior")
        parser.add_option("--fallback-user", dest='fallback_user', metavar='USER', help="fallback review user")
        parser.add_option("--fallback-group", dest='fallback_group', metavar='GROUP', help="fallback review group")
        parser.add_option('-c', '--config', dest='config', metavar='FILE', help='read config file FILE')

        return parser

    def postoptparse(self):
        level = None
        if (self.options.debug):
            level = logging.DEBUG
        elif (self.options.verbose):
            level = logging.INFO

        logging.basicConfig(level=level, format='[%(levelname).1s] %(message)s')
        self.logger = logging.getLogger(self.optparser.prog)

        conf.get_config(override_apiurl=self.options.apiurl)

        if (self.options.osc_debug):
            conf.config['debug'] = True

        self.checker = self.setup_checker()
        if self.options.config:
            self.checker.load_config(self.options.config)

        if self.options.review_mode:
            self.checker.review_mode = self.options.review_mode

        if self.options.fallback_user:
            self.checker.fallback_user = self.options.fallback_user

        if self.options.fallback_group:
            self.checker.fallback_group = self.options.fallback_group

    def setup_checker(self):
        """ reimplement this """
        apiurl = conf.config['apiurl']
        if apiurl is None:
            raise osc.oscerr.ConfigError("missing apiurl")
        user = self.options.user
        group = self.options.group
        # if no args are given, use the current oscrc "owner"
        if user is None and group is None:
            user = conf.get_apiurl_usr(apiurl)

        return self.clazz(apiurl=apiurl,
                          dryrun=self.options.dry,
                          user=user,
                          group=group,
                          logger=self.logger)

    def do_id(self, subcmd, opts, *args):
        """${cmd_name}: check the specified request ids

        ${cmd_usage}
        ${cmd_option_list}
        """
        self.checker.set_request_ids(args)
        return self.checker.check_requests()

    @cmdln.option('-n', '--interval', metavar="minutes", type="int", help="periodic interval in minutes")
    def do_review(self, subcmd, opts, *args):
        """${cmd_name}: check requests that have the specified user or group as reviewer

        ${cmd_usage}
        ${cmd_option_list}
        """
        if self.checker.review_user is None and self.checker.review_group is None:
            raise osc.oscerr.WrongArgs("missing reviewer (user or group)")

        def work():
            self.checker.set_request_ids_search_review()
            return self.checker.check_requests()

        return self.runner(work, opts.interval)

    @cmdln.option('-n', '--interval', metavar="minutes", type="int", help="periodic interval in minutes")
    def do_project(self, subcmd, opts, project, typename):
        """${cmd_name}: check all requests of specified type to specified

        ${cmd_usage}
        ${cmd_option_list}
        """

        def work():
            self.checker.set_request_ids_project(project, typename)
            return self.checker.check_requests()

        return self.runner(work, opts.interval)

    def runner(self, workfunc, interval):
        """ runs the specified callback every <interval> minutes or
        once if interval is None or 0
        """
        class ExTimeout(Exception):
            """raised on timeout"""

        if not interval:
            return workfunc()

        def alarm_called(nr, frame):
            raise ExTimeout()
        signal.signal(signal.SIGALRM, alarm_called)

        while True:
            try:
                workfunc()
            except Exception as e:
                self.logger.exception(e)

            if os.isatty(0):
                self.logger.info("sleeping %d minutes. Press enter to check now ..." % interval)
                signal.alarm(interval * 60)
                try:
                    input()
                except ExTimeout:
                    pass
                signal.alarm(0)
                self.logger.info(f"recheck at {datetime.datetime.now().isoformat()}")
            else:
                self.logger.info("sleeping %d minutes." % interval)
                time.sleep(interval * 60)

            # Reset all memoize session caches which are designed for single
            # tool run and not extended usage.
            memoize_session_reset()

            # Reload checker to flush instance variables and thus any config
            # or caches they may contain.
            self.postoptparse()


if __name__ == "__main__":
    app = CommandLineInterface()
    sys.exit(app.main())
