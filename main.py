import os
import sys

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv


load_dotenv()


def get_household_data(household_id: int) -> dict:
    """Return household, active roommates/preferences, and pantry items."""
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "recipe_app"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "recipe_kb"),
    )

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """SELECT household_id, household_name, currency
               FROM households WHERE household_id = %s""",
            (household_id,),
        )
        household = cursor.fetchone()
        if household is None:
            raise ValueError(f"No household found with id {household_id}.")

        cursor.execute(
            """SELECT r.roommate_id, r.display_name,
                      p.preference_type, p.preference_value, p.strict, p.notes
               FROM roommates AS r
               LEFT JOIN roommate_preferences AS p
                   ON p.roommate_id = r.roommate_id
               WHERE r.household_id = %s AND r.active = TRUE
               ORDER BY r.roommate_id, p.preference_type, p.preference_value""",
            (household_id,),
        )
        roommate_rows = cursor.fetchall()

        # Fold the joined rows into roommate objects with a list of preferences.
        roommates_by_id = {}
        for row in roommate_rows:
            roommate = roommates_by_id.setdefault(
                row["roommate_id"],
                {"roommate_id": row["roommate_id"],
                 "display_name": row["display_name"], "preferences": []},
            )
            if row["preference_type"] is not None:
                roommate["preferences"].append(
                    {"type": row["preference_type"],
                     "value": row["preference_value"],
                     "strict": bool(row["strict"]), "notes": row["notes"]}
                )

        cursor.execute(
            """SELECT ingredient_name, quantity, unit
               FROM pantry_items WHERE household_id = %s
               ORDER BY ingredient_name""",
            (household_id,),
        )
        pantry = cursor.fetchall()
        cursor.close()

        return {
            "household": household,
            "roommates": list(roommates_by_id.values()),
            "pantry": pantry,
        }
    finally:
        connection.close()


def display_household_data(data: dict) -> None:
    """Print the retrieved data in a readable format for a quick workflow demo."""
    household = data["household"]
    print(f"\nHousehold: {household['household_name']} (ID {household['household_id']})")
    print(f"Currency: {household['currency']}\n")

    print("Roommates and constraints:")
    for roommate in data["roommates"]:
        print(f"  - {roommate['display_name']}")
        if not roommate["preferences"]:
            print("      No preferences or restrictions saved")
        for pref in roommate["preferences"]:
            label = "strict" if pref["strict"] else "preference"
            print(f"      {pref['type']}: {pref['value']} ({label})")

    print("\nPantry:")
    if not data["pantry"]:
        print("  No pantry items saved")
    for item in data["pantry"]:
        amount = f" — {item['quantity']} {item['unit'] or ''}" if item["quantity"] is not None else ""
        print(f"  - {item['ingredient_name']}{amount}")


if __name__ == "__main__":
    household_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    try:
        household_data = get_household_data(household_id)
        display_household_data(household_data)
    except (Error, ValueError) as exc:
        print(f"Could not retrieve household data: {exc}", file=sys.stderr)
        print(
            "Check that MySQL is running, recipe_kb.sql has been loaded, "
            "and DB_USER/DB_PASSWORD are correct.",
            file=sys.stderr,
        )
        sys.exit(1)
