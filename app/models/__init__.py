from .geo import District
from .organization import Organization, User, Plan, Subscription
from .messaging import (Contact, MessageTemplate, Campaign, MessageLog, Group)
from .scheduling import CampaignSchedule
from .ops import SendQueue, OptOut, AuditLog, NotificationDismissal
from .wallet import WalletTransaction, Invoice
from .chat import ChatChannel, ChatMessage, ChatReadState
from .pool import PoolPermission, PoolContact
from .imports import ContactImport, ContactImportIssue
from .signup import SignupRequest

# Import API models last so foreign keys resolve correctly
from .api import ApiToken, ApiIdempotency

# Force SQLAlchemy to verify all relationships immediately
from sqlalchemy.orm import configure_mappers
configure_mappers()
