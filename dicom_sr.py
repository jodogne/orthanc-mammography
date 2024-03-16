# Orthanc plugin for mammography
# Copyright (C) 2024 Edouard Chatzopoulos and Sebastien Jodogne,
# ICTEAM UCLouvain, Belgium
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import highdicom
import model
import numpy
import pydicom
import time


def CreateProbabilityOfCancer(probability):
    assert(probability >= 0 and probability <= 100)

    return [
        highdicom.sr.Measurement(
            name = pydicom.sr.codedict.codes.DCM.ProbabilityOfCancer,
            value = probability,
            unit = pydicom.sr.codedict.codes.UCUM.Percent,
        ),
    ]


def apply(retina_net, dicom,
          minimum_score = 0.2,
          title = 'Orthanc Deep Learning for Mammography'):
    start = time.time()
    result = model.apply_model_to_dicom(retina_net, dicom, rescale_boxes=True)
    end = time.time()
    print('Time: %.02f seconds' % (end - start))

    assert(len(result['boxes']) == len(result['scores']))

    # Generic X-ray report, added in DICOM 2023c, so not directly
    # available in pydicom and in DicomSRValidator:
    # https://dicom.nema.org/medical/dicom/2023c/output/chtml/part16/sect_CID_100.html
    reportedProcedure = pydicom.sr.coding.Code(value = '43468-8',
                                               scheme_designator = 'LN',
                                               meaning = 'XR unspecified body region')

    observation_context = highdicom.sr.ObservationContext()

    roi_tracking_id = highdicom.sr.TrackingIdentifier(
        identifier = title,
        uid = highdicom.UID(),
    )

    planar_groups = []

    for i in range(len(result['boxes'])):
        score = result['scores'][i].detach().numpy()
        if score > minimum_score:
            box = result['boxes'][i].detach().numpy()
            assert(len(box) == 4)

            (x1, y1, x2, y2) = box

            planar_groups.append(highdicom.sr.PlanarROIMeasurementsAndQualitativeEvaluations(
                referenced_region = highdicom.sr.ImageRegion(
                    graphic_type = highdicom.sr.GraphicTypeValues.POLYLINE,
                    graphic_data = numpy.array([ [x1, y1], [x2, y1], [x2, y2], [x1,y2], [x1,y1] ]),
                    source_image = highdicom.sr.SourceImageForRegion.from_source_image(dicom, referenced_frame_numbers = None),
                ),
                tracking_identifier = roi_tracking_id,
                # 'SCT' means 'SNOMED-CT'
                # geometric_purpose = highdicom.sr.CodedConcept('75958009', 'SCT', 'Bounded by'),
                measurements = CreateProbabilityOfCancer(score * 100.0),
            ))

    measurement_report = highdicom.sr.MeasurementReport(
        observation_context = observation_context,
        procedure_reported = reportedProcedure,
        imaging_measurements = planar_groups,
    )

    return highdicom.sr.ComprehensiveSR(
        evidence = [ dicom ],
        content = measurement_report,
        series_number = 1,
        series_instance_uid = highdicom.UID(),
        sop_instance_uid = highdicom.UID(),
        instance_number = 1,
    )
