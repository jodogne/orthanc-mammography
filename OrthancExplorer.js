/**
 * Orthanc plugin for mammography
 * Copyright (C) 2024 Edouard Chatzopoulos and Sebastien Jodogne,
 * ICTEAM UCLouvain, Belgium
 *
 * This program is free software: you can redistribute it and/or
 * modify it under the terms of the GNU Affero General Public License
 * as published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 **/

var mammographyButton = null;

$('#instance').live('pagecreate', function() {
  mammographyButton = $('<a>')
      .attr('data-role', 'button')
      .attr('href', '#')
      .attr('data-icon', 'search')
      .attr('data-theme', 'e')
      .text('Deep learning for mammography');

  mammographyButton.insertBefore($('#instance-delete').parent().parent());

  mammographyButton.click(function() {
    if ($.mobile.pageData) {
      $.ajax({
        type: 'POST',
        url: '../mammography-apply',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
          'instance' : $.mobile.pageData.uuid,
        }),
        cache: false,
        success: function(result) {
          console.log(result);
          window.location.assign('explorer.html#series?uuid=' + result.ParentSeries);
        },
        error: function() {
          alert('Cannot apply deep learning model');
        }
      });
    }
  });
});

$('#instance').live('pagebeforeshow', function() {
  mammographyButton.hide();
});

$('#instance').live('pageshow', function() {
  $.ajax({
    url: '../instances/' + $.mobile.pageData.uuid + '/tags?simplify',
    dataType: 'json',
    cache: false,
    success: function(tags) {
      if (tags.Modality == 'MG') {
        mammographyButton.show();
      }
    }
  });
});


$('#study').live('pagebeforecreate', function() {
  var b = $('<a>')
      .attr('data-role', 'button')
      .attr('href', '#')
      .attr('data-icon', 'search')
      .attr('data-theme', 'e')
      .text('Stone Web Viewer (for mammography)');

  b.insertBefore($('#study-delete').parent().parent());
  b.click(function() {
    if ($.mobile.pageData) {
      $.ajax({
        url: '../studies/' + $.mobile.pageData.uuid,
        dataType: 'json',
        cache: false,
        success: function(study) {
          var studyInstanceUid = study.MainDicomTags.StudyInstanceUID;
          window.open('../mammography-viewer/index.html?study=' + studyInstanceUid);
        }
      });
    }
  });
});


$('#series').live('pagebeforecreate', function() {
  var b = $('<a>')
      .attr('data-role', 'button')
      .attr('href', '#')
      .attr('data-icon', 'search')
      .attr('data-theme', 'e')
      .text('Stone Web Viewer (for mammography)');

  b.insertBefore($('#series-delete').parent().parent());
  b.click(function() {
    if ($.mobile.pageData) {
      $.ajax({
        url: '../series/' + $.mobile.pageData.uuid,
        dataType: 'json',
        cache: false,
        success: function(series) {
          $.ajax({
            url: '../studies/' + series.ParentStudy,
            dataType: 'json',
            cache: false,
            success: function(study) {
              var studyInstanceUid = study.MainDicomTags.StudyInstanceUID;
              var seriesInstanceUid = series.MainDicomTags.SeriesInstanceUID;
              window.open('../mammography-viewer/index.html?study=' + studyInstanceUid +
                          '&series=' + seriesInstanceUid);
            }
          });
        }
      });
    }
  });
});
