from datetime import datetime, timezone

from sqlalchemy import select

from app.ai.embedding_text import build_ticket_embedding_text
from app.ai.embeddings import generate_embedding
from app.config import OPENAI_EMBEDDING_MODEL
from app.database import SessionLocal
from app.enums import UserRole
from app.models import Ticket, User


SYNTHETIC_TICKETS = [
    {
        "title": "VPN fails after corporate password reset",
        "description": (
            "The user can sign in to Windows but VPN rejects the new password."
        ),
        "resolution": (
            "Removed the cached VPN credentials, synchronized the new password, "
            "and completed a fresh VPN sign-in."
        ),
    },
    {
        "title": "GlobalProtect authentication failure",
        "description": (
            "GlobalProtect repeatedly requests credentials and never connects."
        ),
        "resolution": (
            "Reset the GlobalProtect authentication session and asked the user "
            "to complete the MFA prompt during reconnection."
        ),
    },
    {
        "title": "Remote access credentials rejected",
        "description": (
            "Remote access stopped working after the user's password expired."
        ),
        "resolution": (
            "Confirmed the password change, cleared saved remote-access "
            "credentials, and reauthenticated the VPN client."
        ),
    },
    {
        "title": "Outlook repeatedly asks for password",
        "description": (
            "Outlook displays a password prompt whenever email is synchronized."
        ),
        "resolution": (
            "Removed stale Microsoft 365 credentials from Credential Manager "
            "and signed the user back into Outlook."
        ),
    },
    {
        "title": "Outlook MFA sign-in loop",
        "description": (
            "Outlook returns to the sign-in screen after the MFA challenge."
        ),
        "resolution": (
            "Cleared the Office identity cache, restarted Outlook, and completed "
            "a new modern-authentication and MFA session."
        ),
    },
    {
        "title": "Microsoft 365 desktop apps show unlicensed",
        "description": (
            "Outlook and Word report that the user's Microsoft 365 account is "
            "not activated."
        ),
        "resolution": (
            "Removed the expired Office activation token and reactivated the "
            "applications with the user's licensed account."
        ),
    },
    {
        "title": "Historical claims client crash opening records",
        "description": (
            "The claims client closes immediately when a specific claim is opened."
        ),
        "resolution": (
            "Cleared the claims client cache and repaired the local application "
            "profile before reopening the claim."
        ),
    },
    {
        "title": "Claims system login failure",
        "description": (
            "The user can access other corporate systems but cannot sign in to "
            "the claims application."
        ),
        "resolution": (
            "Resynchronized the user's claims security group membership and "
            "started a new single-sign-on session."
        ),
    },
    {
        "title": "Claims application cannot save claim notes",
        "description": (
            "Saving claim notes produces a validation error with no missing fields."
        ),
        "resolution": (
            "Updated the claims client to the supported version and cleared its "
            "local form cache."
        ),
    },
    {
        "title": "Network printer unavailable",
        "description": (
            "The department printer appears offline for one workstation."
        ),
        "resolution": (
            "Removed the stale printer connection and added the printer again "
            "from the correct print server queue."
        ),
    },
    {
        "title": "Documents stuck in printer queue",
        "description": (
            "Multiple print jobs remain in the queue and no pages are printed."
        ),
        "resolution": (
            "Cleared the failed jobs, restarted the Print Spooler service, and "
            "submitted a successful test page."
        ),
    },
    {
        "title": "Laptop loses network through docking station",
        "description": (
            "The laptop has Wi-Fi access but no wired network when docked."
        ),
        "resolution": (
            "Updated the docking-station network driver and reset the wired "
            "network adapter."
        ),
    },
]


def seed_resolved_tickets() -> None:
    with SessionLocal() as db:
        requester = db.scalars(
            select(User)
            .where(User.role == UserRole.ADMIN)
            .order_by(User.id)
        ).first()
        if requester is None:
            raise RuntimeError(
                "Create an ADMIN user before seeding resolved tickets"
            )

        try:
            for ticket_data in SYNTHETIC_TICKETS:
                ticket = db.scalars(
                    select(Ticket).where(
                        Ticket.title == ticket_data["title"]
                    )
                ).first()

                if ticket is None:
                    ticket = Ticket(
                        requester_id=requester.id,
                        title=ticket_data["title"],
                        description=ticket_data["description"],
                    )
                    db.add(ticket)

                content_changed = (
                    ticket.description != ticket_data["description"]
                    or ticket.resolution != ticket_data["resolution"]
                )
                ticket.description = ticket_data["description"]
                ticket.resolution = ticket_data["resolution"]
                ticket.status = "RESOLVED"

                if (
                    content_changed
                    or ticket.embedding is None
                    or ticket.embedding_model != OPENAI_EMBEDDING_MODEL
                ):
                    embedding_text = build_ticket_embedding_text(
                        title=ticket.title,
                        description=ticket.description,
                        resolution=ticket.resolution,
                    )
                    ticket.embedding = generate_embedding(embedding_text)
                    ticket.embedding_model = OPENAI_EMBEDDING_MODEL
                    ticket.embedding_updated_at = datetime.now(timezone.utc)
                    print(f"Prepared synthetic ticket: {ticket.title}")
                else:
                    print(f"Skipped unchanged ticket: {ticket.title}")

            db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"Seeded {len(SYNTHETIC_TICKETS)} resolved synthetic tickets.")


if __name__ == "__main__":
    seed_resolved_tickets()
