/**
* This file is part of ORB-SLAM3
*
* Copyright (C) 2017-2021 Carlos Campos, Richard Elvira, Juan J. Gómez Rodríguez, José M.M. Montiel and Juan D. Tardós, University of Zaragoza.
* Copyright (C) 2014-2016 Raúl Mur-Artal, José M.M. Montiel and Juan D. Tardós, University of Zaragoza.
*
* ORB-SLAM3 is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
* License as published by the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* ORB-SLAM3 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
* the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License along with ORB-SLAM3.
* If not, see <http://www.gnu.org/licenses/>.
*/

#ifndef MAPOBJECT_H
#define MAPOBJECT_H

#include <opencv2/core/core.hpp>
#include <Eigen/Core>
#include <mutex>
#include <atomic>
#include <deque>
#include <vector>
#include <string>

namespace ORB_SLAM3
{

class MapObject
{
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    MapObject(const std::string &label, int classId, const cv::Point3f &posWorld);

    long unsigned int Id() const;
    std::string GetLabel() const;
    int GetClassId() const;

    cv::Point3f GetPosWorld() const;
    void SetPosWorld(const cv::Point3f &posWorld);

    cv::Point3f GetSize() const;
    void SetSize(const cv::Point3f &size);

    float GetConfidence() const;
    void SetConfidence(float conf);

    int GetObservationCount() const;
    void IncrementObservationCount();

    bool IsVLMRequested() const;
    void SetVLMRequested(bool requested);

    cv::Rect2i GetLastBBox() const;
    void SetLastBBox(const cv::Rect2i &bbox);

    void AddObservation(const cv::Point3f &posWorld);
    std::vector<cv::Point3f> GetObservations() const;

private:
    static std::atomic<unsigned long> nNextId;

    long unsigned int mnId;
    std::string mLabel;
    int mClassId;
    cv::Point3f mPosWorld;
    cv::Point3f mSize;
    float mConfidence;
    int mObsCount;
    bool mVLMRequested;
    cv::Rect2i mLastBBox;
    std::deque<cv::Point3f> mRawObservations;
    const size_t mMaxObsWindow = 20;

    mutable std::mutex mMutex;
};

} // namespace ORB_SLAM3

#endif // MAPOBJECT_H
