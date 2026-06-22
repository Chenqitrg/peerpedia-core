# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""User CRUD — database only, ``session.flush()`` only.

Functions
---------
create_user             New user with bcrypt password hash
get_user                By ID or name
get_user_by_name        Exact name match
update_user_reputation  Write reputation dict (flush only)
follow_user / unfollow_user / get_followers / get_following / get_follower_count
derive_anonymous_name   Display name from anonymous hash (e.g. "anon-a3f2...")

Reviewer's checklist
--------------------
- All functions call ``session.flush()``, not ``session.commit()``.
"""

import secrets
import uuid

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Follow, User


def generate_anonymous_name() -> str:
    """Generate a random cross-disciplinary anonymous name (100×100 = 10,000 combinations)."""
    return _pick_anonymous_name(secrets.randbelow(10000))


def derive_anonymous_name(seed: str) -> str:
    """Derive a stable anonymous name from a seed string.

    Same seed → same name every time.  Use when the directory ID is
    already deterministic (e.g. ``_derive_anonymous_id``).
    """
    import hashlib
    idx = int(hashlib.sha256(seed.encode()).hexdigest()[:4], 16) % 10000
    return _pick_anonymous_name(idx)


def _pick_anonymous_name(idx: int) -> str:
    adjectives = [
        # 天文
        "星云", "极光", "天狼", "猎户", "白矮", "超新", "脉冲", "日冕", "陨石", "银河",
        # 物理
        "量子", "光子", "引力", "超导", "弦论", "暗物质", "反物质", "核聚变", "等离子", "熵增",
        # 数学
        "素数", "拓扑", "张量", "黎曼", "哥德尔", "斐波那契", "混沌", "分形", "对偶", "递归",
        # 计算机
        "图灵", "香农", "布尔", "冯诺依曼", "并行", "加密", "协议栈", "缓存", "寄存器", "堆栈",
        # 生物
        "线粒体", "突触", "端粒", "核糖体", "神经元", "干细胞", "基因", "拟态", "共生", "进化",
        # 医学
        "免疫", "抗体", "疫苗", "激素", "代谢", "基因组", "轴突", "再生", "诊断", "预后",
        # 化学
        "催化", "晶格", "同位素", "稀土", "聚合", "氧化", "配位", "胶体", "裂解", "合成",
        # 地质
        "玄武", "硅基", "沉积", "地幔", "板块", "熔岩", "断层", "化石", "冰期", "碳循环",
        # 人文
        "楔形", "甲骨", "梵文", "苏美尔", "玛雅", "拜占庭", "史诗", "神话", "图腾", "方言",
        # 社科
        "博弈", "共识", "声誉", "信任", "互惠", "规范", "信号", "偏见", "启发", "偏好",
    ]
    nouns = [
        # 天文
        "星云", "极光", "天狼星", "猎户座", "白矮星", "超新星", "脉冲星", "日冕", "陨石", "银河",
        # 物理
        "量子", "光子", "引力波", "超导体", "弦论家", "暗物质", "反物质", "核聚变", "等离子", "熵",
        # 数学
        "素数", "拓扑", "张量", "黎曼假设", "哥德尔数", "斐波那契", "混沌", "分形", "对偶", "递归",
        # 计算机
        "图灵机", "香农熵", "布尔代数", "冯诺依曼", "并行计算", "加密算法", "协议栈", "缓存", "寄存器", "堆栈",
        # 生物
        "线粒体", "突触", "端粒", "核糖体", "神经元", "干细胞", "基因组", "拟态", "共生体", "进化树",
        # 医学
        "免疫系统", "抗体", "疫苗", "激素", "代谢", "基因组学", "轴突", "再生医学", "诊断", "预后",
        # 化学
        "催化剂", "晶格", "同位素", "稀土元素", "聚合物", "氧化物", "配位体", "胶体", "裂解", "合成",
        # 地质
        "玄武岩", "硅基", "沉积物", "地幔", "板块", "熔岩", "断层", "化石", "冰期", "碳循环",
        # 人文
        "楔形文字", "甲骨文", "梵文", "苏美尔人", "玛雅人", "拜占庭", "史诗", "神话", "图腾", "方言",
        # 社科
        "博弈论", "共识", "声誉", "信任", "互惠", "规范", "信号", "偏见", "启发", "偏好",
    ]
    adj = adjectives[idx // 100 % len(adjectives)]
    noun = nouns[idx % 100 % len(nouns)]
    return f"{adj}{noun}"


def create_user(
    session: Session,
    name: str,
    affiliation: str = "",
    password_hash: str = "",
    email: str = "",
) -> User:
    u = User(
        id=str(uuid.uuid4()),
        name=name,
        password_hash=password_hash,
        email=email,
        affiliation=affiliation,
    )
    session.add(u)
    session.flush()
    return u


def get_user(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def get_user_by_name(session: Session, name: str) -> User | None:
    return session.query(User).filter(User.name == name).first()


def list_users(session: Session) -> list[User]:
    return session.query(User).order_by(User.created_at.desc()).all()


def search_users(session: Session, query: str, limit: int | None = None, offset: int = 0) -> list[User]:
    """Fuzzy search users by name (case-insensitive ILIKE)."""
    q = session.query(User).filter(User.name.ilike(f"%{query}%"))
    q = q.order_by(User.created_at.desc())
    if limit is not None:
        q = q.limit(limit).offset(offset)
    return q.all()


def get_users_by_ids(session: Session, user_ids: set[str]) -> list[User]:
    """Return User records for the given IDs.

    Raises ValueError if any *user_ids* are not found — missing users
    at this point means data corruption (review from nonexistent user).
    """
    if not user_ids:
        return []
    users = session.query(User).filter(User.id.in_(user_ids)).all()
    found = {u.id for u in users}
    missing = user_ids - found
    if missing:
        raise ValueError(f"Users not found: {', '.join(sorted(missing))}")
    return users


def update_user_public_key(session: Session, user_id: str, pubkey_hex: str) -> User:
    """Set the public_key for a user. Raises ValueError if user not found."""
    # TODO(perf): loads full User for single-field update. Use targeted UPDATE.
    u = session.get(User, user_id)
    if u is None:
        raise ValueError(f"User {user_id} not found")
    u.public_key = pubkey_hex
    session.flush()
    return u


def update_user_salt(session: Session, user_id: str, salt_hex: str) -> User:
    """Set the scrypt salt for a user. Raises ValueError if user not found."""
    # TODO(perf): loads full User for single-field update. Use targeted UPDATE.
    u = session.get(User, user_id)
    if u is None:
        raise ValueError(f"User {user_id} not found")
    u.salt = salt_hex
    session.flush()
    return u


def update_user_reputation(session: Session, user_id: str, reputation: dict) -> User:
    # TODO(perf): loads full User for single-field update. Use targeted UPDATE.
    u = session.get(User, user_id)
    if u is None:
        raise ValueError(f"User {user_id} not found")
    u.reputation = reputation
    session.flush()
    return u


# ── Follow ───────────────────────────────────────────────────────────────


def follow_user(session: Session, follower_id: str, followed_id: str) -> Follow:
    if follower_id == followed_id:
        raise ValueError("A user cannot follow themselves")
    f = Follow(follower_id=follower_id, followed_id=followed_id)
    session.add(f)
    session.flush()
    return f


def unfollow_user(session: Session, follower_id: str, followed_id: str) -> None:
    f = session.query(Follow).filter(Follow.follower_id == follower_id, Follow.followed_id == followed_id).first()
    if f:
        session.delete(f)
        session.flush()


def is_following(session: Session, follower_id: str, followed_id: str) -> bool:
    return session.query(Follow).filter(Follow.follower_id == follower_id, Follow.followed_id == followed_id).first() is not None


def get_followers(session: Session, user_id: str) -> list[User]:
    # TODO(perf): two queries instead of one JOIN.  Use:
    #   session.query(User).join(Follow, User.id==Follow.follower_id).filter(Follow.followed_id==user_id)
    follower_ids = session.query(Follow.follower_id).filter(Follow.followed_id == user_id).all()
    ids = [row[0] for row in follower_ids]
    return session.query(User).filter(User.id.in_(ids)).all() if ids else []


def get_following(session: Session, user_id: str) -> list[User]:
    # TODO(perf): two queries instead of one JOIN.  Use:
    #   session.query(User).join(Follow, User.id==Follow.followed_id).filter(Follow.follower_id==user_id)
    followed_ids = session.query(Follow.followed_id).filter(Follow.follower_id == user_id).all()
    ids = [row[0] for row in followed_ids]
    return session.query(User).filter(User.id.in_(ids)).all() if ids else []


def get_follower_count(session: Session, user_id: str) -> int:
    return session.query(Follow).filter(Follow.followed_id == user_id).count()


def get_following_count(session: Session, user_id: str) -> int:
    return session.query(Follow).filter(Follow.follower_id == user_id).count()
