from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.result import Result
from app.models.race import Race
from app.models.constructor import Constructor
from app.models.elo import ConstructorElo

INITIAL_ELO = 1500.0
K_FACTOR = 32.0

def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

def update_elo(rating: float, expected: float, actual: float, k: float = K_FACTOR) -> float:
    return round(rating + k * (actual - expected), 4)

async def compute_constructor_elo(db: AsyncSession) -> dict:
    # Get all races ordered by date
    races_result = await db.execute(select(Race).order_by(Race.season, Race.round))
    races = races_result.scalars().all()

    # Get all constructors
    constructors_result = await db.execute(select(Constructor))
    constructors = constructors_result.scalars().all()

    # Initialise ratings
    ratings = {c.id: INITIAL_ELO for c in constructors}
    history = []

    for race in races:
        # Get results for this race ordered by position
        results_result = await db.execute(
            select(Result)
            .where(Result.race_id == race.id)
            .where(Result.position != None)
            .order_by(Result.position)
        )
        results = results_result.scalars().all()

        if len(results) < 2:
            continue

        # Get unique constructors in this race with their best position
        constructor_positions = {}
        for r in results:
            if r.constructor_id not in constructor_positions:
                constructor_positions[r.constructor_id] = r.position

        constructor_list = sorted(constructor_positions.items(), key=lambda x: x[1])

        # Round-robin Elo updates between all constructor pairs
        updates = {cid: ratings.get(cid, INITIAL_ELO) for cid, _ in constructor_list}

        for i in range(len(constructor_list)):
            for j in range(i + 1, len(constructor_list)):
                cid_a, pos_a = constructor_list[i]
                cid_b, pos_b = constructor_list[j]

                rating_a = ratings.get(cid_a, INITIAL_ELO)
                rating_b = ratings.get(cid_b, INITIAL_ELO)

                # Lower position = better result, so A beat B
                actual_a = 1.0 if pos_a < pos_b else 0.0
                actual_b = 1.0 - actual_a

                exp_a = expected_score(rating_a, rating_b)
                exp_b = expected_score(rating_b, rating_a)

                updates[cid_a] = updates[cid_a] + K_FACTOR * (actual_a - exp_a)
                updates[cid_b] = updates[cid_b] + K_FACTOR * (actual_b - exp_b)

        # Save history and update ratings
        for cid, new_rating in updates.items():
            old_rating = ratings.get(cid, INITIAL_ELO)
            history.append(ConstructorElo(
                constructor_id=cid,
                race_id=race.id,
                elo_before=round(old_rating, 2),
                elo_after=round(new_rating, 2),
                date=race.date or f"{race.season}-01-01"
            ))
            ratings[cid] = new_rating

    # Bulk save
    db.add_all(history)
    await db.commit()

    # Return current standings
    constructor_map = {c.id: c.name for c in constructors}
    return {
        "ratings": sorted(
            [{"constructor": constructor_map.get(cid, "Unknown"),
              "constructor_id": cid,
              "elo": round(rating, 2)}
             for cid, rating in ratings.items()],
            key=lambda x: x["elo"],
            reverse=True
        )
    }