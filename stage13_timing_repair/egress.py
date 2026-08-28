from __future__ import annotations

import multiprocessing as mp
import os
import queue
import socket
import struct
import time
from dataclasses import dataclass
from typing import Any

from src.path_oram import PathORAM


HEADER = struct.Struct("!QII")  # public random epoch, public slot, public flags=0


def _wait_until(deadline_ns: int) -> int:
    """Actual wall-clock barrier in the dedicated egress process.

    A continuous monotonic wait deliberately spends one core during the short
    protected epoch. It avoids Windows timer-quantum wakeups; OS preemption is
    still measured as real release slip rather than hidden or rewritten.
    """
    while time.perf_counter_ns() < deadline_ns:
        pass
    return time.perf_counter_ns()


def _windows_affinity(mask: int | None = None) -> int:
    if os.name != "nt":
        available = os.sched_getaffinity(0)
        prior = sum(1 << cpu for cpu in available)
        if mask is not None: os.sched_setaffinity(0, {cpu for cpu in range(64) if mask & (1 << cpu)})
        return prior
    import ctypes
    kernel32=ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype=ctypes.c_void_p
    kernel32.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
    kernel32.GetProcessAffinityMask.restype=ctypes.c_int
    kernel32.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    kernel32.SetProcessAffinityMask.restype=ctypes.c_int
    process=kernel32.GetCurrentProcess()
    process_mask=ctypes.c_size_t(); system_mask=ctypes.c_size_t()
    if not kernel32.GetProcessAffinityMask(process,ctypes.byref(process_mask),ctypes.byref(system_mask)):
        raise OSError("GetProcessAffinityMask failed")
    if mask is not None and not kernel32.SetProcessAffinityMask(process,ctypes.c_size_t(mask)):
        raise OSError("SetProcessAffinityMask failed")
    return int(process_mask.value)


def _thread_affinity(mask: int) -> None:
    if os.name != "nt":
        os.sched_setaffinity(0, {cpu for cpu in range(64) if mask & (1 << cpu)})
        return
    import ctypes
    kernel32=ctypes.windll.kernel32
    kernel32.GetCurrentThread.restype=ctypes.c_void_p
    kernel32.SetThreadAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    kernel32.SetThreadAffinityMask.restype=ctypes.c_size_t
    if not kernel32.SetThreadAffinityMask(kernel32.GetCurrentThread(),ctypes.c_size_t(mask)):
        raise OSError("SetThreadAffinityMask failed")


def _receiver_process(ready_q: mp.Queue, arrival_q: mp.Queue, stop_event: Any,
                      receiver_mask: int, commit_eligible: Any) -> None:
    _windows_affinity(receiver_mask)
    _thread_affinity(receiver_mask)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0)); listener.listen(1)
    ready_q.put(listener.getsockname())
    receiver, _peer = listener.accept(); listener.close()
    receiver.settimeout(0.05)
    effect_ledger: set[tuple[int, int]] = set()
    while not stop_event.is_set():
        try:
            header = b""
            while len(header) < 4:
                chunk = receiver.recv(4 - len(header))
                if not chunk: return
                header += chunk
            frame_size = struct.unpack("!I", header)[0]
            data = b""
            while len(data) < frame_size:
                chunk = receiver.recv(frame_size - len(data))
                if not chunk: return
                data += chunk
        except socket.timeout:
            continue
        t7 = time.perf_counter_ns()
        if len(data) < HEADER.size:
            continue
        epoch, slot, _flags = HEADER.unpack_from(data)
        t8 = time.perf_counter_ns()
        if epoch == 0:
            continue
        commit = bool(slot == 5 and commit_eligible.value)
        if commit:
            effect_ledger.add((epoch, slot))
        t9 = time.perf_counter_ns() if commit else 0
        arrival_q.put({"epoch": epoch, "slot": slot, "t7": t7, "t8": t8,
                       "receiver_bytes": len(data), "t9": t9,
                       "effect_committed": (epoch, slot) in effect_ledger})
    receiver.close()


def _transport_process(command_q: mp.Queue, result_q: mp.Queue, arrival_q: mp.Queue,
                       receiver_address: tuple[str, int], sender_mask: int,
                       ready_count: Any, proposal_flag: Any, done_flag: Any,
                       commit_eligible: Any) -> None:
    _windows_affinity(sender_mask)
    _thread_affinity(sender_mask)
    sender = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sender.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sender.connect(receiver_address)
    # Prewarm the persistent socket and receiver before accepting experiments.
    prewarm = HEADER.pack(0, 0, 0) + os.urandom(240)
    sender.sendall(struct.pack("!I", len(prewarm)) + prewarm)
    time.sleep(0.01)
    result_q.put({"ready": True, "address_family": "AF_INET", "connection_prewarmed": True,
                  "sender_affinity_mask": sender_mask})

    while True:
        command = command_q.get()
        if command["kind"] == "STOP":
            break
        if command["kind"] != "EPISODE":
            raise RuntimeError(command)
        epoch = int(command["epoch"])
        horizon = int(command["horizon"])
        delta_ns = int(command["delta_ns"])
        start_ns = time.perf_counter_ns() + 50_000_000
        frame_bytes = int(command["frame_bytes"])
        mode = str(command["mode"])
        frames = [HEADER.pack(epoch, slot, 0) + os.urandom(frame_bytes - HEADER.size) for slot in range(1, horizon + 1)]
        oram = PathORAM(128, epoch & 0xFFFFFFFF, 4, 7)

        def protected_paths(slot: int) -> list[int]:
            leaves=[]
            for access_index in range(3):
                _,physical=oram.access((slot*3+access_index)%128,"read")
                leaves.append(int(physical["leaf"]))
            return leaves

        def transmit(frame: bytes) -> None:
            sender.sendall(struct.pack("!I", len(frame)) + frame)
        slots: list[dict[str, Any]] = []
        ready_count.value = 0; proposal_flag.value = 0; done_flag.value = 0; commit_eligible.value = 0
        result_q.put({"episode_started": epoch, "start_ns": start_ns})

        if mode == "M2":
            # Fixed count/size, but application-ready messages are released as
            # soon as the boundary process observes them: deliberately unshaped.
            slot = 1
            consumed = 0
            while not bool(done_flag.value):
                if int(ready_count.value) > consumed and slot < horizon:
                    consumed += 1
                    leaves=protected_paths(slot)
                    t3 = time.perf_counter_ns(); t4 = t3
                    t5 = time.perf_counter_ns(); t6 = time.perf_counter_ns(); transmit(frames[slot - 1])
                    slots.append({"slot": slot, "t3": t3, "t4": t4, "t5": t5, "t6": t6,
                                  "release_slip_ns": t4 - t3, "real_internal": True,
                                  "oram_physical_leaves": leaves})
                    slot += 1
                else:
                    time.sleep(0)
            while slot < horizon:
                leaves=protected_paths(slot)
                t3 = time.perf_counter_ns(); t4 = t3
                t5 = time.perf_counter_ns(); t6 = time.perf_counter_ns(); transmit(frames[slot - 1])
                slots.append({"slot": slot, "t3": t3, "t4": t4, "t5": t5, "t6": t6,
                              "release_slip_ns": 0, "real_internal": False,
                              "oram_physical_leaves": leaves})
                slot += 1
            leaves=protected_paths(horizon); t3 = time.perf_counter_ns(); t4 = t3
            commit_eligible.value = int(bool(proposal_flag.value))
            t5 = time.perf_counter_ns(); t6 = time.perf_counter_ns(); transmit(frames[-1])
            slots.append({"slot": horizon, "t3": t3, "t4": t4, "t5": t5, "t6": t6,
                          "release_slip_ns": 0, "real_internal": bool(proposal_flag.value),
                          "oram_physical_leaves": leaves})
        elif mode == "M3":
            commit_ready = False
            for slot in range(1, horizon + 1):
                leaves=protected_paths(slot)
                deadline = start_ns + slot * delta_ns
                if slot == horizon:
                    # Sample commit eligibility at a fixed guard point, never
                    # in the release critical section. A proposal arriving
                    # after the guard is a bounded overflow and cannot slip
                    # the public deadline or cause an unauthorized effect.
                    guard_ns = deadline - min(1_000_000, max(100_000, delta_ns // 3))
                    _wait_until(guard_ns)
                    commit_ready = bool(proposal_flag.value)
                    commit_eligible.value = int(commit_ready)
                _wait_until(deadline)
                t4 = time.perf_counter_ns()  # release decision at the true boundary
                t5 = time.perf_counter_ns()  # fixed prebuilt frame selected/copied
                t6 = time.perf_counter_ns()
                transmit(frames[slot - 1])
                # Occupancy is reconstructed only after the public epoch;
                # neither the sender nor receiver touches secret-updated
                # mailbox cache lines in the release/receive critical path.
                slots.append({"slot": slot, "t3": deadline, "t4": t4, "t5": t5, "t6": t6,
                              "release_slip_ns": t4 - deadline, "real_internal": False,
                              "oram_physical_leaves": leaves})
            # Drain completion notification without changing the public schedule.
            drain_deadline = time.perf_counter_ns() + 200_000_000
            while not bool(done_flag.value) and time.perf_counter_ns() < drain_deadline:
                time.sleep(0)
            produced = min(int(ready_count.value), horizon - 1)
            for index in range(produced):
                slots[index]["real_internal"] = True
            slots[-1]["real_internal"] = commit_ready
        else:
            raise ValueError(mode)

        arrivals: dict[int, dict[str, Any]] = {}
        receive_deadline = time.perf_counter_ns() + 1_000_000_000
        while len(arrivals) < horizon and time.perf_counter_ns() < receive_deadline:
            try:
                arrival = arrival_q.get(timeout=0.05)
            except queue.Empty:
                continue
            if int(arrival["epoch"]) == epoch:
                arrivals[int(arrival["slot"])] = arrival
        if len(arrivals) != horizon:
            raise RuntimeError("receiver did not observe the complete public epoch")
        for row in slots:
            arrival = arrivals[int(row["slot"])]
            row.update({"t7": int(arrival["t7"]), "t8": int(arrival["t8"]),
                        "t9": int(arrival["t9"]), "receiver_bytes": int(arrival["receiver_bytes"])})
        final_real = bool(slots[-1]["real_internal"])
        # Strip real/cover status from the observer view. It remains only in
        # trusted instrumentation for effect/overflow auditing.
        observer = [{k: v for k, v in row.items() if k != "real_internal"} for row in slots]
        result_q.put({"epoch": epoch, "observer_slots": observer,
                      "private_slot_occupancy": [bool(row["real_internal"]) for row in slots],
                      "final_real": final_real, "effect_count": int(arrivals[horizon]["effect_committed"]),
                      "worker_done_by_epoch_end": bool(done_flag.value)})

    sender.close()


@dataclass
class EgressEpisode:
    epoch: int
    start_ns: int
    mode: str
    horizon: int
    delta_ns: int
    frame_bytes: int
    ready_count: Any
    proposal_flag: Any
    done_flag: Any
    result_q: mp.Queue

    def enqueue(self) -> int:
        t2 = time.perf_counter_ns()
        self.ready_count.value += 1
        return t2

    def proposal(self) -> int:
        timestamp = time.perf_counter_ns()
        self.proposal_flag.value = 1
        return timestamp

    def done(self) -> int:
        timestamp = time.perf_counter_ns()
        self.done_flag.value = 1
        return timestamp

    def wait(self, timeout: float = 5.0) -> dict[str, Any]:
        return self.result_q.get(timeout=timeout)


class PersistentEgressShaper:
    """Persistent dedicated process controlling actual loopback TCP release."""

    def __init__(self) -> None:
        self.original_affinity = _windows_affinity()
        bits=[1 << cpu for cpu in range(64) if self.original_affinity & (1 << cpu)]
        if len(bits)<3: raise RuntimeError("Stage-13 high-assurance shaper requires at least three logical CPUs")
        self.sender_affinity=bits[-1]; self.receiver_affinity=bits[-2]
        parent_affinity=self.original_affinity ^ self.sender_affinity ^ self.receiver_affinity
        context = mp.get_context("spawn")
        self.command_q = context.Queue()
        self.result_q = context.Queue()
        self.arrival_q = context.Queue()
        self.receiver_ready_q = context.Queue()
        self.receiver_stop = context.Event()
        self.ready_count = context.RawValue("i", 0)
        self.proposal_flag = context.RawValue("i", 0)
        self.done_flag = context.RawValue("i", 0)
        self.commit_eligible = context.RawValue("i", 0)
        self.receiver_process = context.Process(target=_receiver_process,
            args=(self.receiver_ready_q,self.arrival_q,self.receiver_stop,self.receiver_affinity,self.commit_eligible),
            name="stage13-receiver",daemon=True)
        self.receiver_process.start()
        receiver_address = self.receiver_ready_q.get(timeout=10)
        self.process = context.Process(target=_transport_process,
                                       args=(self.command_q,self.result_q,self.arrival_q,receiver_address,self.sender_affinity,
                                             self.ready_count,self.proposal_flag,self.done_flag,self.commit_eligible),
                                       name="stage13-egress", daemon=True)
        self.process.start()
        ready = self.result_q.get(timeout=10)
        if not ready.get("ready"):
            raise RuntimeError("egress process failed to initialize")
        _windows_affinity(parent_affinity)
        self.counter = 1

    def start(self, mode: str, horizon: int, delta_ms: float, frame_bytes: int) -> EgressEpisode:
        if mode not in {"M2", "M3"}:
            raise ValueError(mode)
        epoch = (os.getpid() << 32) ^ self.counter ^ int.from_bytes(os.urandom(4), "big")
        self.counter += 1
        delta_ns = int(delta_ms * 1e6)
        self.command_q.put({"kind": "EPISODE", "epoch": epoch, "mode": mode,
                            "horizon": horizon, "delta_ns": delta_ns,
                            "frame_bytes": frame_bytes})
        acknowledgement = self.result_q.get(timeout=5)
        if int(acknowledgement.get("episode_started", -1)) != epoch:
            raise RuntimeError("egress episode-start synchronization failed")
        start_ns = int(acknowledgement["start_ns"])
        return EgressEpisode(epoch, start_ns, mode, horizon, delta_ns, frame_bytes,
                             self.ready_count,self.proposal_flag,self.done_flag,self.result_q)

    def close(self) -> None:
        if self.process.is_alive():
            self.command_q.put({"kind": "STOP"})
            self.process.join(timeout=3)
        if self.process.is_alive():
            self.process.terminate(); self.process.join(timeout=1)
        self.receiver_stop.set()
        if self.receiver_process.is_alive():
            self.receiver_process.terminate(); self.receiver_process.join(timeout=1)
        _windows_affinity(self.original_affinity)

    def __enter__(self) -> "PersistentEgressShaper": return self
    def __exit__(self, *_exc: object) -> None: self.close()
