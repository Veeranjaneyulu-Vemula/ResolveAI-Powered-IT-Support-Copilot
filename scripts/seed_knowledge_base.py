from sqlalchemy import select

from app.ai.chunking import add_chunk_context, chunk_text
from app.ai.embeddings import generate_embedding
from app.config import OPENAI_EMBEDDING_MODEL
from app.database import SessionLocal
from app.models import KnowledgeArticle, KnowledgeChunk


SOURCE_NAME = "ResolveAI Synthetic IT Knowledge Base"

SYNTHETIC_ARTICLES = [
    {
        "title": "VPN Authentication After a Password Change",
        "category": "VPN / Network",
        "content": """
Users may be unable to authenticate to the corporate VPN after changing an
expired or forgotten password. A common symptom is that Windows accepts the new
password while the VPN client continues to report invalid credentials. Confirm
that the user can sign in to another corporate service with the new password
and verify that the account is not locked. Ask whether the VPN client is using
saved credentials or an old connection profile.

Remove only the saved VPN credential for the affected profile, then completely
exit and reopen the VPN client. Have the user enter the current username and
password manually. If multifactor authentication is enabled, confirm that the
user receives and approves the current MFA prompt. Do not repeatedly retry a
locked account because repeated failures can extend the lockout.

If authentication still fails, verify that password synchronization has
completed between the identity service and remote-access service. Escalate to
the identity or network support team when the account works elsewhere but the
VPN gateway consistently rejects the verified credentials.
""",
    },
    {
        "title": "GlobalProtect Connection Troubleshooting",
        "category": "VPN / Network",
        "content": """
GlobalProtect connection failures can appear as a permanent Connecting state,
repeated credential prompts, an unavailable portal, or a successful login with
no internal network access. First record the exact client message and determine
whether the failure happens before authentication, during MFA, or after the
tunnel connects. Confirm that the device has normal internet access and that
its date and time are correct.

For authentication loops, sign out of the client, close it, reopen it, and
complete one fresh sign-in. Check for an MFA notification that may be waiting
on the registered device. For portal or gateway errors, confirm that the
configured portal address matches the approved support documentation. Avoid
disabling endpoint protection or changing security controls as a workaround.

When the tunnel connects but internal resources remain unavailable, capture
the assigned VPN address and the affected resource names. Restarting the client
is reasonable, but repeated reinstalls should not be the first action.
Escalate persistent gateway, certificate, or routing errors to network support
with the timestamp, client message, and affected user information.
""",
    },
    {
        "title": "MFA Enrollment and Verification Problems",
        "category": "Authentication",
        "content": """
MFA problems include missing approval prompts, repeated verification requests,
rejected one-time codes, and access attempts tied to an old phone. Begin by
confirming that the user is responding to the newest prompt and that the device
time is set automatically. Ask whether the user recently replaced the phone,
changed the phone number, removed the authenticator application, or completed
a password reset.

If the registered method is still available, have the user open the
authenticator application directly and check for a pending request. A one-time
code must be entered before it expires. Do not ask the user to read an approval
code or password to support staff. Unexpected prompts should be denied and
reported as a possible security event.

If no registered method is usable, follow the approved identity-verification
process before resetting MFA enrollment. After a reset, the user should enroll
a supported method and test it with a normal sign-in. Escalate when identity
verification cannot be completed, the account is locked, or prompts continue
after successful re-enrollment.
""",
    },
    {
        "title": "Outlook Repeated Password Prompts",
        "category": "Microsoft 365",
        "content": """
Outlook may repeatedly request a password when cached Microsoft 365 credentials
or authentication tokens are stale. Confirm whether Outlook on the web works
and whether other desktop Office applications show the same account problem.
Record whether the prompt appears immediately, during mailbox synchronization,
or after an MFA request.

Close Outlook before changing cached credentials. Remove only stale entries
associated with the affected Microsoft 365 account from the operating system
credential store. Reopen Outlook and complete a fresh modern-authentication
sign-in, including MFA when requested. Verify that the account displayed in
Outlook is the intended work account and not an old personal or test account.

If web access also fails, investigate the account, password, MFA, or service
health rather than repeatedly rebuilding the Outlook profile. If web access
works but the desktop prompt continues, update Office and collect the Outlook
authentication symptoms for Microsoft 365 support. Avoid deleting local data
files until synchronization and backup status are understood.
""",
    },
    {
        "title": "Microsoft 365 Sign-In and Licensing",
        "category": "Microsoft 365",
        "content": """
Microsoft 365 applications can display unlicensed product, sign-in required, or
account error messages when an activation token is expired or the wrong account
is selected. Check whether the user has an assigned license and whether the
same identity can access Microsoft 365 in a browser. Confirm that the device
date, time, and network connection are correct.

In the affected application, review the account page and sign out obsolete
work, personal, or test identities. Close all Office applications before
clearing an expired activation token through the approved support procedure.
Reopen one application, sign in with the licensed work account, and allow
activation to finish before opening additional applications.

If browser sign-in fails, troubleshoot authentication or MFA first. If browser
access succeeds but activation does not, record the displayed license and error
information and escalate to Microsoft 365 support. Do not assign licenses or
alter subscription settings unless the operator is authorized to perform those
administrative actions.
""",
    },
    {
        "title": "Claims Application Authentication Guide",
        "category": "Claims Application",
        "content": """
A user may be able to access Windows and Microsoft 365 while the claims
application rejects sign-in. Determine whether the application uses direct
credentials or corporate single sign-on. Record the exact error, the time of
the attempt, and whether another authorized claims user can sign in from the
same environment.

For single-sign-on failures, have the user close the claims application and
browser sessions, then start one new corporate sign-in. Confirm that the
required claims access group is still assigned and that recent role changes
have synchronized. A password reset may require a new session, but support
should not manually change application permissions without an approved access
request.

If the account is recognized but access is denied, compare the assigned role
with the requested claims function. If the account is not recognized, escalate
to the claims identity support team with the username, timestamp, and error
message. Never test access by sharing another user's credentials or by granting
temporary excessive permissions.
""",
    },
    {
        "title": "Claims Application Crash Troubleshooting",
        "category": "Claims Application",
        "content": """
Claims application crashes should be separated into startup crashes, crashes
when opening a claim, and crashes during a specific action such as saving
notes. Record the affected claim identifier using approved synthetic or
non-sensitive test data, the action that caused the crash, and whether the
problem affects one claim or many claims.

Restart the application and reproduce the issue once. Confirm that the client
version is supported and that the most recent approved update completed.
Clearing the application cache or recreating the local application profile can
resolve corrupted local state, but preserve required logs before clearing
diagnostic data. Do not delete business records or modify claims data as a
troubleshooting shortcut.

If only one claim triggers the failure, escalate with the claim identifier and
timestamp for application-data review. If many users are affected after an
update, treat it as a possible service incident and notify application support.
Include the client version, error text, and reproducible steps.
""",
    },
    {
        "title": "Policy Application Access Requests",
        "category": "Policy Application",
        "content": """
Policy application access must follow approved role and manager authorization
procedures. First determine whether the user has never had access, changed job
functions, or previously had access that stopped working. New access and
restoration of a technical failure are different request types.

For new or expanded access, verify that an approved request identifies the
required business role and appropriate manager or application-owner approval.
Support engineers should not select elevated permissions on the user's behalf.
After provisioning, allow normal directory synchronization time and ask the
user to begin a new sign-in session.

For previously working access, confirm that the account is active, the expected
group remains assigned, and the application is not experiencing a broader
outage. Escalate unexplained removals to the policy application owner. Never
copy another employee's permissions without validating least-privilege
requirements and receiving the required approval.
""",
    },
    {
        "title": "Network Printer Connectivity Guide",
        "category": "Printer",
        "content": """
When a network printer appears offline, determine whether the issue affects one
workstation, one department, or every user of the printer. Confirm that the
workstation has network access and identify the approved print-server queue.
Check whether jobs are stuck locally or reach the server queue.

For a single workstation, remove a stale connection to the printer and add it
again from the approved print server. If jobs remain stuck, cancel the failed
jobs and restart the Print Spooler through the approved support procedure, then
send one test page. Do not repeatedly submit additional jobs because this can
make queue diagnosis harder.

If all users are affected, check the printer's power, network status, consumable
alerts, and print-server availability. Escalate hardware faults to the printer
support team and server queue failures to infrastructure support. Record the
printer name, queue, location, affected users, and visible error.
""",
    },
    {
        "title": "Laptop and Dock Network Connectivity",
        "category": "Hardware / Network",
        "content": """
A laptop that works on Wi-Fi but loses network access through a docking station
usually requires the wired path to be tested separately. Confirm that the dock
has power, the network cable is connected, and the wired adapter appears in the
operating system. Test another approved cable or dock port when available.

Disconnect and reconnect the dock, then allow the wired adapter to initialize.
Check whether the adapter is disabled or reports a driver problem. Install only
the approved docking-station firmware or network-driver update for the device
model. Avoid changing organization-wide network or security settings to repair
one workstation.

If multiple docks at the same location fail, investigate the network port or
local infrastructure. If one laptop fails on several known-good docks, collect
the adapter status and driver version for endpoint support. Document whether
Wi-Fi remains functional, because that helps distinguish a dock problem from a
general network outage.
""",
    },
]


def seed_knowledge_base() -> None:
    with SessionLocal() as db:
        try:
            for article_data in SYNTHETIC_ARTICLES:
                article = db.scalars(
                    select(KnowledgeArticle).where(
                        KnowledgeArticle.title == article_data["title"]
                    )
                ).first()

                if article is None:
                    article = KnowledgeArticle(
                        title=article_data["title"],
                        content=article_data["content"].strip(),
                        category=article_data["category"],
                        source_name=SOURCE_NAME,
                    )
                    db.add(article)
                    db.flush()

                article.content = article_data["content"].strip()
                article.category = article_data["category"]
                article.source_name = SOURCE_NAME
                expected_chunks = [
                    add_chunk_context(
                        article_title=article.title,
                        category=article.category,
                        content=chunk,
                    )
                    for chunk in chunk_text(article.content)
                ]
                existing_chunks = sorted(
                    article.chunks,
                    key=lambda chunk: chunk.chunk_index,
                )

                chunks_are_current = (
                    len(existing_chunks) == len(expected_chunks)
                    and all(
                        chunk.chunk_index == index
                        and chunk.content == expected_chunks[index]
                        and chunk.embedding is not None
                        and chunk.embedding_model == OPENAI_EMBEDDING_MODEL
                        for index, chunk in enumerate(existing_chunks)
                    )
                )

                if chunks_are_current:
                    print(f"Skipped unchanged article: {article.title}")
                    continue

                article.chunks.clear()
                db.flush()

                for chunk_index, content in enumerate(expected_chunks):
                    article.chunks.append(
                        KnowledgeChunk(
                            chunk_index=chunk_index,
                            content=content,
                            embedding=generate_embedding(content),
                            embedding_model=OPENAI_EMBEDDING_MODEL,
                        )
                    )

                print(
                    f"Prepared article: {article.title} "
                    f"({len(expected_chunks)} chunks)"
                )

            db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"Seeded {len(SYNTHETIC_ARTICLES)} synthetic KB articles.")


if __name__ == "__main__":
    seed_knowledge_base()
