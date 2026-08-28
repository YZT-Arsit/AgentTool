"""OPTIONAL_PRIVATE_STATE_BACKEND only.

This simulator may model outsourced logical records.  It MUST NOT be used to
claim privacy for named Agent selection, Agent dispatch, Tool invocation, or
external execution identity.  The active control-virtualization design does
not import this module.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import mean
from typing import Any

@dataclass
class Block:
    block_id: int
    value: Any

class PathORAM:
    """Functional Path-ORAM mechanics for synthetic access-trace experiments.

    Payload encryption is abstracted. The server-side tree, position map, stash,
    remapping, full-path transfer, and greedy eviction are implemented. This is
    research simulation code, not a production cryptographic ORAM.
    """
    def __init__(self, n_blocks: int, seed: int, bucket_size: int = 4, height: int | None = None):
        self.n_blocks=n_blocks; self.z=bucket_size; self.height=height if height is not None else max(1,math.ceil(math.log2(max(2,n_blocks))))
        self.leaves=1 << self.height; self.rng=random.Random(seed)
        self.tree={i: [] for i in range((1 << (self.height+1))-1)}
        self.position={i:self.rng.randrange(self.leaves) for i in range(n_blocks)}
        self.stash={}
        self.stash_samples=[]; self.max_stash=len(self.stash)
        # Fast legal initialization: place each block in its deepest compatible
        # bucket with capacity, otherwise retain it in the client stash.
        ids=list(range(n_blocks));self.rng.shuffle(ids)
        for bid in ids:
            block=Block(bid,f"initial_{bid}")
            placed=False
            for node in reversed(self.path(self.position[bid])):
                if len(self.tree[node])<self.z:
                    self.tree[node].append(block);placed=True;break
            if not placed:self.stash[bid]=block
        self.stash_samples.clear(); self.max_stash=len(self.stash)

    def path(self, leaf: int) -> list[int]:
        node=0; out=[0]
        for level in range(self.height):
            bit=(leaf >> (self.height-level-1)) & 1
            node=node*2+1+bit; out.append(node)
        return out

    def _compatible(self, block_id: int, node: int) -> bool:
        return node in self.path(self.position[block_id])

    def _evict(self, leaf: int) -> None:
        path=self.path(leaf)
        for node in reversed(path):
            candidates=[bid for bid in sorted(self.stash) if self._compatible(bid,node)]
            capacity=self.z-len(self.tree[node])
            for bid in candidates[:capacity]: self.tree[node].append(self.stash.pop(bid))

    def access(self, block_id: int, operation: str="read", value: Any=None) -> tuple[Any,dict[str,Any]]:
        if block_id not in self.position: raise KeyError(block_id)
        old_leaf=self.position[block_id]; physical_path=self.path(old_leaf)
        for node in physical_path:
            for block in self.tree[node]: self.stash[block.block_id]=block
            self.tree[node]=[]
        if block_id not in self.stash: raise AssertionError("logical block lost")
        prior=self.stash[block_id].value
        if operation=="write": self.stash[block_id].value=value
        elif operation!="read": raise ValueError(operation)
        self.position[block_id]=self.rng.randrange(self.leaves)
        self._evict(old_leaf)
        self.stash_samples.append(len(self.stash)); self.max_stash=max(self.max_stash,len(self.stash))
        trace={"leaf":old_leaf,"physical_path":physical_path,"tree_height":self.height,
               "buckets_touched":len(physical_path),"physical_blocks_transferred":2*len(physical_path)*self.z}
        return prior,trace

    def all_real_ids(self) -> list[int]:
        ids=list(self.stash)
        for bucket in self.tree.values(): ids += [b.block_id for b in bucket]
        return ids

    def assert_invariants(self) -> None:
        ids=self.all_real_ids()
        if sorted(ids)!=list(range(self.n_blocks)): raise AssertionError("missing or duplicate block")
        for node,bucket in self.tree.items():
            if len(bucket)>self.z: raise AssertionError("bucket overflow")
            for b in bucket:
                if not self._compatible(b.block_id,node): raise AssertionError("path constraint violated")
        if set(self.position)!=set(range(self.n_blocks)): raise AssertionError("position map incomplete")

    @property
    def mean_stash(self): return mean(self.stash_samples) if self.stash_samples else len(self.stash)
