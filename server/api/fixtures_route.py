"""Drop a synthetic report and receive only its printed results."""

from fastapi import APIRouter, HTTPException

from fixtures.pack import catalog, is_unreadable, load_pack, lookup, public_fixture

router = APIRouter(prefix="/fixtures", tags=["fixtures"])


@router.get("")
def list_fixtures() -> dict:
    return {"fixtures": catalog(load_pack())}


@router.get("/{fixture_id}")
def read_fixture(fixture_id: str) -> dict:
    scenario = lookup(fixture_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Unknown synthetic report")
    if is_unreadable(scenario):
        raise HTTPException(status_code=422, detail="This photo is not clear enough to read")
    try:
        return public_fixture(scenario)
    except ValueError:
        raise HTTPException(status_code=422, detail="This report could not be read") from None
