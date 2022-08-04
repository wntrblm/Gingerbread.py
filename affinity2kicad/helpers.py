# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT


def add_eurorack_mounting_holes(pcb, hp=0):
    offset = 5.08 * hp
    pcb.add_slotted_hole(7.5 + offset, 3, 3.25, 4)
    pcb.add_slotted_hole(7.5 + offset, pcb.bbox[3] - 3, 3.25, 4)


def add_1u_hybrid_mounting_holes(pcb, hp=0):
    offset = 5.08 * hp
    pcb.add_slotted_hole(7.5 + offset, 4 / 2 - 3.22 / 2, 8, 3.22)
    pcb.add_slotted_hole(
        7.5 + offset, pcb.bbox[3] - 4 / 2 + 3.22 / 2, 8, 3.22
    )
