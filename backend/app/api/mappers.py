"""Перевод представлений сервисов в схемы ответов API."""
from app.api import schemas
from app.domain.draft import Change
from app.domain.merge import MergeItem
from app.domain.states import KtOfferState
from app.keitaro.models import CatalogOffer, KtReference
from app.services.views import (
    CampaignSummary,
    CampaignView,
    CreateReport,
    OfferView,
    PreviewView,
    ReferenceDefaults,
    StreamView,
)


def offer_out(view: OfferView) -> schemas.OfferOut:
    offer = view.offer
    return schemas.OfferOut(
        offer_id=offer.offer_id, name=offer.name, geo=offer.geo, state=view.state.value,
        weight=offer.weight, kt_weight=offer.kt_weight, pinned=offer.pinned,
    )


def stream_out(view: StreamView) -> schemas.StreamOut:
    return schemas.StreamOut(
        id=view.id, keitaro_id=view.keitaro_id, name=view.name, position=view.position,
        has_offers=bool(view.offers), dirty=view.dirty, weight_sum=view.weight_sum,
        offers=[offer_out(o) for o in view.offers], notes=view.notes,
    )


def campaign_out(view: CampaignView) -> schemas.CampaignOut:
    return schemas.CampaignOut(
        id=view.id, keitaro_id=view.keitaro_id, name=view.name, alias=view.alias, fetched_at=view.fetched_at,
        streams=[stream_out(s) for s in view.streams],
    )


def summary_out(summary: CampaignSummary) -> schemas.CampaignSummaryOut:
    return schemas.CampaignSummaryOut(**vars(summary))


def change_out(change: Change) -> schemas.ChangeOut:
    return schemas.ChangeOut(
        kind=change.kind, offer_id=change.offer.offer_id, name=change.offer.name,
        from_weight=change.from_weight, to_weight=change.to_weight, note=change.note,
    )


def merge_item_out(item: MergeItem) -> schemas.MergeItemOut:
    return schemas.MergeItemOut(
        key=item.key, kind=item.kind, offer_id=item.offer_id, message=item.message, resolution=item.resolution,
    )


def kt_offer_out(offer: KtOfferState) -> schemas.KtOfferOut:
    return schemas.KtOfferOut(offer_id=offer.offer_id, name=offer.name, geo=offer.geo, weight=offer.weight)


def preview_out(view: PreviewView) -> schemas.PreviewOut:
    return schemas.PreviewOut(
        stream=stream_out(view.stream),
        keitaro_offers=[kt_offer_out(o) for o in view.keitaro_offers],
        changes=[change_out(c) for c in view.changes],
        merge_items=[merge_item_out(i) for i in view.merge_items],
        unresolved=[merge_item_out(i) for i in view.unresolved],
        can_push=view.can_push,
    )


def report_out(report: CreateReport) -> schemas.CreateReportOut:
    return schemas.CreateReportOut(
        ok=report.ok, campaign_id=report.campaign_id, name=report.name, alias=report.alias,
        steps=[schemas.StepOut(name=s.name, description=s.description, status=s.status, error=s.error) for s in report.steps],
    )


def reference_out(ref: KtReference) -> schemas.ReferenceOut:
    return schemas.ReferenceOut(id=ref.ref_id, name=ref.name)


def defaults_out(defaults: ReferenceDefaults) -> schemas.DefaultsOut:
    return schemas.DefaultsOut(**vars(defaults))


def catalog_offer_out(offer: CatalogOffer) -> schemas.OfferSearchOut:
    return schemas.OfferSearchOut(offer_id=offer.offer_id, name=offer.name, geo=offer.geo)
