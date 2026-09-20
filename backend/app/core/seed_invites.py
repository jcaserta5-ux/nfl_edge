"""
Seed initial invite codes for admin use.
Run: docker compose exec backend python -m app.core.seed_invites
"""
import asyncio
import secrets
import string
from app.db.session import AsyncSessionLocal
from app.db.models import InviteCode

INVITE_COUNT = 10
CODE_LENGTH = 16


def generate_code() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(CODE_LENGTH))


async def seed():
    async with AsyncSessionLocal() as session:
        codes = []
        for _ in range(INVITE_COUNT):
            code = InviteCode(code=generate_code(), is_active=True)
            session.add(code)
            codes.append(code.code)
        await session.commit()
        print(f"✅ Created {INVITE_COUNT} invite codes:")
        for c in codes:
            print(f"  {c}")


if __name__ == "__main__":
    asyncio.run(seed())
