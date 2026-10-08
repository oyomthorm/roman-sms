"""
Flask CLI commands for Roman SMS.

Run from the project root with the local venv active:
    flask --help
    flask seed-all
    flask grant kampalafit 500
    flask reconcile
"""
import click

from flask.cli import with_appcontext

from app.extensions import db
from app.models import Organization, User, Plan
from app.services import wallet as wallet_svc
from app.services.audit import log as audit


def register_cli(app):

    # ==================================================================
    # Seeding
    # ==================================================================

    @app.cli.command('seed-all')
    @with_appcontext
    def seed_all():
        """
        Run every seed step in the correct order.

        Idempotent — safe to re-run after deploys or on a fresh database.

        Steps:
          1. scripts/seed.py            — master org, system org, admin, plans
          2. scripts/seed_districts.py  — district reference data
        """
        import subprocess
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent

        scripts = [
            ('seed.py',           'Master org, system org, admin, tier plans'),
            ('seed_districts.py', 'District reference data'),
        ]

        for filename, label in scripts:
            path = project_root / 'scripts' / filename
            if not path.exists():
                raise click.ClickException(
                    f'{path} not found. Is the project complete?')

            click.echo(f'--- {label} ---')
            result = subprocess.run(
                [sys.executable, str(path)],
                cwd=str(project_root),
            )
            if result.returncode != 0:
                raise click.ClickException(
                    f'{filename} failed with exit code {result.returncode}')

        click.echo()
        click.echo('All seeds complete.')

    @app.cli.command('seed')
    @with_appcontext
    def seed_cmd():
        """
        Alias for scripts/seed.py — creates master, system org, admin, plans.

        Prefer `flask seed-all` which also seeds districts.
        """
        import subprocess
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, str(project_root / 'scripts' / 'seed.py')],
            cwd=str(project_root),
        )
        if result.returncode != 0:
            raise click.ClickException('seed.py failed.')

    @app.cli.command('seed-districts')
    @with_appcontext
    def seed_districts_cmd():
        """Alias for scripts/seed_districts.py."""
        import subprocess
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable,
             str(project_root / 'scripts' / 'seed_districts.py')],
            cwd=str(project_root),
        )
        if result.returncode != 0:
            raise click.ClickException('seed_districts.py failed.')

    # ==================================================================
    # Credits
    # ==================================================================

    @app.cli.command('grant')
    @click.argument('org_slug')
    @click.argument('amount', type=int)
    @click.option('--note', default='',
                  help='Free-text note stored on the ledger row.')
    @with_appcontext
    def grant(org_slug, amount, note):
        """
        Grant credits to an associate from the master reserve.

        Example:
            flask grant kampalafit 500 --note "welcome credits"
        """
        org = Organization.query.filter_by(slug=org_slug).first()
        if not org:
            raise click.ClickException(f'No org with slug {org_slug}')
        if org.is_master or org.is_system:
            raise click.ClickException(
                f'{org.name} is a protected org. '
                f'Use fund-master or fund-platform.')

        if amount <= 0:
            raise click.ClickException('Amount must be positive.')

        try:
            master_id = wallet_svc.master_org_id()
            wallet_svc.transfer(
                master_id, org.id, amount,
                reason='manual_topup',
                note=note or 'Granted by CLI',
            )
            db.session.commit()
        except wallet_svc.InsufficientCredits as e:
            db.session.rollback()
            raise click.ClickException(
                f'Master wallet has insufficient credits: {e}')
        except wallet_svc.WalletError as e:
            db.session.rollback()
            raise click.ClickException(str(e))

        click.echo(f'Granted {amount} to {org.name}.')
        click.echo(f'  {org.name}: {wallet_svc.get_balance(org.id):,}')
        click.echo(f'  Master:     {wallet_svc.get_balance(master_id):,}')
        audit('wallet_grant_cli',
              f'org={org.slug} amount={amount}',
              org_id=org.id)

    @app.cli.command('fund-master')
    @click.argument('amount', type=int)
    @click.option('--note', default='Manual master top-up')
    @with_appcontext
    def fund_master(amount, note):
        """
        Add credits to the master operating wallet.

        Example:
            flask fund-master 50000 --note "Q1 budget"
        """
        if amount <= 0:
            raise click.ClickException('Amount must be positive.')

        master = Organization.query.filter_by(is_master=True).first()
        if not master:
            raise click.ClickException('Master org not found. Run seed.')

        wallet_svc.credit(master.id, amount,
                          reason='master_topup', note=note)
        db.session.commit()
        click.echo(f'Added {amount} credits. '
                   f'Master balance: {wallet_svc.get_balance(master.id)}.')

    @app.cli.command('fund-platform')
    @click.argument('amount', type=int)
    @click.option('--note', default='Platform sending budget')
    @with_appcontext
    def fund_platform(amount, note):
        """
        Allocate credits from the master reserve to the system org.

        Atomic: debits master, credits platform.

        Example:
            flask fund-platform 500 --note "Pool sending budget"
        """
        if amount <= 0:
            raise click.ClickException('Amount must be positive.')

        try:
            master_id = wallet_svc.master_org_id()
            platform = Organization.query.filter_by(is_system=True).first()
            if not platform:
                raise click.ClickException('System org not found. Run seed.')

            wallet_svc.transfer(
                master_id, platform.id, amount,
                reason='platform_allocation',
                note=note,
            )
            db.session.commit()
        except wallet_svc.InsufficientCredits as e:
            db.session.rollback()
            raise click.ClickException(
                f'Master wallet has insufficient credits: {e}')
        except wallet_svc.WalletError as e:
            db.session.rollback()
            raise click.ClickException(str(e))

        click.echo(f'Allocated {amount:,} credits.')
        click.echo(f'  Master:   '
                   f'{wallet_svc.get_balance(master_id):,}')
        click.echo(f'  Platform: '
                   f'{wallet_svc.get_balance(platform.id):,}')        

    # ==================================================================
    # Organizations and users
    # ==================================================================

    @app.cli.command('create-org')
    @click.argument('name')
    @click.argument('slug')
    @click.argument('admin_email')
    @click.option('--brand', default=None,
                  help='Sender prefix. Defaults to the org name.')
    @click.option('--password', default='ChangeMe123!',
                  help='Initial password for the associate admin.')
    @with_appcontext
    def create_org(name, slug, admin_email, brand, password):
        """
        Create an associate org and its admin user.

        Example:
            flask create-org "Kampalafit" kampalafit owner@kfit.co.ug
        """
        from app.services import orgs as orgs_svc

        try:
            org, admin = orgs_svc.create_associate(
                name=name, slug=slug, brand_name=brand or name,
                admin_email=admin_email, admin_password=password,
            )
        except orgs_svc.OrgError as e:
            raise click.ClickException(str(e))

        click.echo(f'Created {org.name} (id={org.id}) and admin '
                   f'{admin.email}.')

    @app.cli.command('reset-password')
    @click.argument('email')
    @click.option('--password', prompt=True, hide_input=True,
                  confirmation_prompt=True,
                  help='New password.')
    @with_appcontext
    def reset_password(email, password):
        """
        Reset any user's password by email.

        Example:
            flask reset-password admin@romansms.local
        """
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            raise click.ClickException(f'No user with email {email}')
        if len(password) < 8:
            raise click.ClickException(
                'Password must be at least 8 characters.')

        user.set_password(password)
        db.session.commit()
        audit('user_password_reset_cli',
              f'user={user.email}',
              org_id=user.org_id, actor_id=None)
        click.echo(f'Password updated for {user.email}.')

    # ==================================================================
    # Campaigns
    # ==================================================================

    @app.cli.command('bulk-send')
    @click.argument('org_slug')
    @click.argument('body')
    @click.option('--group', default=None,
                  help='Send only to this group.')
    @click.option('--district', default=None,
                  help='Send only to contacts in this district.')
    @click.option('--name', default='cli-campaign',
                  help='Campaign name for the audit trail.')
    @with_appcontext
    def bulk_send(org_slug, body, group, district, name):
        """
        Queue a campaign from the CLI. Uses the same service as the web
        form, so all rules apply (entitlements, opt-outs, wallet debit).

        Example:
            flask bulk-send kampalafit "Hello {{name}}" --group VIP
        """
        from app.services import campaigns as camp_svc
        from app.services import groups as groups_svc
        from app.services import geo as geo_svc

        org = Organization.query.filter_by(slug=org_slug).first()
        if not org:
            raise click.ClickException(f'No org with slug {org_slug}')
        if org.is_master or org.is_system:
            raise click.ClickException(
                f'{org.name} is a protected org. '
                f'Use the master console for platform sends.')

        group_obj = groups_svc.find_by_name(org, group) if group else None
        if group and not group_obj:
            raise click.ClickException(
                f'No group named {group!r} in {org.name}.')

        district_obj = (geo_svc.find_by_name(district)
                        if district else None)
        if district and not district_obj:
            raise click.ClickException(
                f'No district named {district!r}.')

        try:
            campaign, segs = camp_svc.create_campaign(
                org, name=name, body=body,
                group_id=group_obj.id if group_obj else None,
                group_name=group_obj.name if group_obj else None,
                district_id=district_obj.id if district_obj else None,
                district_name=district_obj.name if district_obj else None,
            )
        except camp_svc.CampaignError as e:
            raise click.ClickException(str(e))

        click.echo(f'Queued campaign {campaign.id}: '
                   f'{campaign.total} recipients, {segs} credits.')

    # ==================================================================
    # Pahappa / EgoSMS
    # ==================================================================

    @app.cli.command('egosms-balance')
    @click.option('--wallet', default=None,
                  type=click.Choice(['local', 'international']),
                  help='Which wallet to query. Omit for local.')
    @with_appcontext
    def egosms_balance(wallet):
        """
        Check the Pahappa master wallet balance.

        Example:
            flask egosms-balance
            flask egosms-balance --wallet international
        """
        from app.services.egosms_client import EgoSMSClient

        client = EgoSMSClient()
        click.echo(f'Endpoint: {client.endpoint}')
        click.echo(f'Sandbox:  {client.sandbox}')

        if not client.username:
            raise click.ClickException(
                'EGOSMS_USERNAME is not set in .env')

        resp = client.balance(wallet_type=wallet)
        if resp.ok:
            if resp.balance is None:
                click.echo('OK, but balance field was missing.')
                click.echo(f'Raw: {resp.raw}')
            else:
                click.echo(f'Balance: {resp.balance}')
        else:
            click.echo(f'Failed: {resp.message}')
            if resp.raw:
                click.echo(f'Raw: {resp.raw}')
            raise click.ClickException('Balance query failed.')

    @app.cli.command('egosms-test')
    @click.argument('number')
    @click.option('--sandbox', is_flag=True,
                  help='Use the sandbox endpoint.')
    @click.option('--message',
                  default='Roman SMS connectivity test.',
                  help='Message body.')
    @with_appcontext
    def egosms_test(number, sandbox, message):
        """
        Send one real message and print the full response. Useful for
        confirming credentials before trusting the worker.

        Example:
            flask egosms-test 256700123456
            flask egosms-test 256700123456 --sandbox
        """
        from app.services.egosms_client import EgoSMSClient

        if sandbox:
            app.config['EGOSMS_SANDBOX'] = True

        client = EgoSMSClient()
        click.echo(f'Endpoint: {client.endpoint}')
        click.echo(f'To:       {number}')
        click.echo('-' * 50)

        resp = client.send_batch([{
            'number': number,
            'message': message,
        }])

        click.echo(f'ok:              {resp.ok}')
        click.echo(f'status:          {resp.status}')
        click.echo(f'message:         {resp.message}')
        click.echo(f'cost:            {resp.cost}')
        click.echo(f'follow_up_code:  {resp.follow_up_code}')
        if resp.raw:
            click.echo('-' * 50)
            click.echo(f'raw:             {resp.raw}')

        if not resp.ok:
            raise click.ClickException('Send failed.')

    # ==================================================================
    # Maintenance
    # ==================================================================

    @app.cli.command('reconcile')
    @with_appcontext
    def reconcile():
        """
        Verify wallet ledgers and credit sources.

        Delegates to scripts/reconcile.py so the logic lives in one
        place. Exits non-zero on any failure.
        """
        import subprocess
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable,
             str(project_root / 'scripts' / 'reconcile.py')],
            cwd=str(project_root),
        )
        if result.returncode != 0:
            raise click.ClickException('Reconciliation failed.')

    @app.cli.command('expire-subs')
    @with_appcontext
    def expire_subs():
        """
        Flip expired active subscriptions to status='expired'.

        Runs nightly via cron in production. Safe to run manually.

        Example:
            flask expire-subs
        """
        from datetime import datetime
        from app.models import Subscription

        now = datetime.utcnow()
        n = (Subscription.query
             .filter(Subscription.status == 'active',
                     Subscription.expires_at < now)
             .update({'status': 'expired'}, synchronize_session=False))
        db.session.commit()
        click.echo(f'Expired {n} subscription(s).')

    @app.cli.command('backup')
    @with_appcontext
    def backup():
        """
        Run a database backup now. Uses scripts/backup.py so the same
        path the cron job uses.

        Example:
            flask backup
        """
        import subprocess
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, str(project_root / 'scripts' / 'backup.py')],
            cwd=str(project_root),
        )
        if result.returncode != 0:
            raise click.ClickException('backup.py failed.')

    # ==================================================================
    # Diagnostics
    # ==================================================================

    @app.cli.command('info')
    @with_appcontext
    def info():
        """
        Print a summary of the current environment: counts, balances,
        configuration flags. Useful for sanity-checking after a deploy.

        Example:
            flask info
        """
        from app.models import (District, Contact, Campaign, MessageLog,
                                SendQueue, Invoice, Subscription)

        click.echo('=== Roman SMS environment ===')
        click.echo()
        click.echo(f'Database:        '
                   f'{app.config["SQLALCHEMY_DATABASE_URI"].split("@")[-1]}')
        click.echo(f'Sandbox mode:    '
                   f'{"ON" if app.config.get("EGOSMS_SANDBOX") else "off"}')
        click.echo(f'Public URL:      '
                   f'{app.config.get("PUBLIC_BASE_URL") or "(not set)"}')
        click.echo(f'Webhook token:   '
                   f'{"set" if app.config.get("WEBHOOK_TOKEN") else "(not set)"}')
        click.echo(f'Mail backend:    {app.config.get("MAIL_BACKEND")}')
        click.echo(f'Log format:      {app.config.get("LOG_FORMAT")}')
        click.echo()

        click.echo('=== Rows ===')
        click.echo(f'Organizations:   {Organization.query.count()}')
        click.echo(f'  master:        '
                   f'{Organization.query.filter_by(is_master=True).count()}')
        click.echo(f'  system:        '
                   f'{Organization.query.filter_by(is_system=True).count()}')
        click.echo(f'  associates:    '
                   f'{Organization.query.filter_by(is_master=False, is_system=False).count()}')
        click.echo(f'Users:           {User.query.count()}')
        click.echo(f'Districts:       {District.query.count()}')
        click.echo(f'Plans:           {Plan.query.count()} '
                   f'({Plan.query.filter_by(is_active=True).count()} active)')
        click.echo(f'Contacts:        {Contact.query.count()}')
        click.echo(f'Campaigns:       {Campaign.query.count()}')
        click.echo(f'Messages:        {MessageLog.query.count()}')
        click.echo(f'Queue pending:   '
                   f'{SendQueue.query.filter_by(status="pending").count()}')
        click.echo(f'Invoices unpaid: '
                   f'{Invoice.query.filter_by(status="unpaid").count()}')
        click.echo(f'Active subs:     '
                   f'{Subscription.query.filter_by(status="active").count()}')
        click.echo()

        click.echo('=== Wallets ===')
        for o in Organization.query.order_by(Organization.id).all():
            bal = wallet_svc.get_balance(o.id)
            click.echo(f'  {o.name:28} {bal:>10,} credits')