#!/usr/bin/env python3
"""A missing creator is not invented where a primary reuse grant waives attribution."""
from __future__ import annotations
import re
from urllib.parse import urlparse


def rights_record_complete(record):
    name=record.get('license') or record.get('licence') or ''
    url=record.get('license_url') or record.get('licence_url') or ''
    source=record.get('source_page') or ''
    creator=record.get('creator') or record.get('artist')
    if not (name and url and source):return False
    if creator:return True  # existing creator/source/terms provenance requirement
    if not (record.get('licence_terms_verified') is True and record.get('asset_verified') is True and record.get('attribution_required') is False):return False
    basis=record.get('source_reuse_basis')
    if basis=='primary_public_domain_declaration':
        return urlparse(source).hostname=='commons.wikimedia.org' and ('public domain' in name.lower() or 'cc0' in name.lower()) and '/publicdomain/' in url
    if basis=='standard_unsplash_provider_license':
        asset=urlparse(record.get('original_url',''))
        return asset.hostname=='images.unsplash.com' and bool(re.fullmatch(r'/photo-[0-9]+-[A-Za-z0-9]+',asset.path)) and url=='https://unsplash.com/license' and bool(record.get('assetMetadataSha256'))
    return False
