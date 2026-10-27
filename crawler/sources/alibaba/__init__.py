"""阿里巴巴：社招按站点配置，校招按集团开放批次。"""
from crawler.sources.alibaba.portal import (
    DEFAULT_PORTALS, SUPPORTED_PORTALS, organization_assignments, parse_post, run,
)
from crawler.sources.alibaba.client import Batch, CampusClient, parse_batches
from crawler.sources.alibaba.society import SocietyClient, load_sites
