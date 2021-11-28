# Copyright (c) 2021 Alethea Katherine Flowers.
# Published under the standard MIT License.
# Full text available at: https://opensource.org/licenses/MIT


def add_eurorack_mounting_holes(converter, hp=0):
    offset = 5.08 * hp
    converter.pcb.add_slotted_hole(7.5 + offset, 3, 3.25, 4)
    converter.pcb.add_slotted_hole(7.5 + offset, converter.bbox[3] - 3, 3.25, 4)
    converter.pcb.add_horizontal_measurement(
        0,
        3,
        7.5 + offset,
        3,
        crossbar_offset=3,
        text_size=0.4,
        text_thickness=0.06,
        arrow_length=0.8,
        arrow_span=0.3,
    )
    converter.pcb.add_horizontal_measurement(
        0,
        converter.bbox[3] - 3,
        7.5 + offset,
        converter.bbox[3] - 3,
        crossbar_offset=-3,
        text_size=0.4,
        text_thickness=0.06,
        arrow_length=0.8,
        arrow_span=0.3,
    )
    converter.pcb.add_vertical_measurement(
        7.5 + offset,
        0,
        7.5 + offset,
        3,
        crossbar_offset=-7.5,
        text_size=0.4,
        text_thickness=0.06,
        arrow_length=0.8,
        arrow_span=0.3,
    )
    converter.pcb.add_vertical_measurement(
        7.5 + offset,
        converter.bbox[3] - 3,
        7.5 + offset,
        converter.bbox[3],
        crossbar_offset=-7.5,
        text_size=0.4,
        text_thickness=0.06,
        arrow_length=0.8,
        arrow_span=0.3,
    )


def add_1u_hybrid_mounting_holes(converter, hp=0):
    offset = 5.08 * hp
    converter.pcb.add_slotted_hole(7.5 + offset, 4 / 2 - 3.22 / 2, 8, 3.22)
    converter.pcb.add_slotted_hole(
        7.5 + offset, converter.bbox[3] - 4 / 2 + 3.22 / 2, 8, 3.22
    )
    converter.pcb.add_horizontal_measurement(
        0,
        3,
        7.5 + offset,
        3,
        crossbar_offset=3,
        text_size=0.4,
        text_thickness=0.06,
        arrow_length=0.8,
        arrow_span=0.3,
    )
    converter.pcb.add_horizontal_measurement(
        0,
        converter.bbox[3] - 3,
        7.5 + offset,
        converter.bbox[3] - 3,
        crossbar_offset=-3,
        text_size=0.4,
        text_thickness=0.06,
        arrow_length=0.8,
        arrow_span=0.3,
    )
    converter.pcb.add_vertical_measurement(
        7.5 + offset,
        0,
        7.5 + offset,
        3,
        crossbar_offset=-7.5,
        text_size=0.4,
        text_thickness=0.06,
        arrow_length=0.8,
        arrow_span=0.3,
    )
    converter.pcb.add_vertical_measurement(
        7.5 + offset,
        converter.bbox[3] - 3,
        7.5 + offset,
        converter.bbox[3],
        crossbar_offset=-7.5,
        text_size=0.4,
        text_thickness=0.06,
        arrow_length=0.8,
        arrow_span=0.3,
    )
