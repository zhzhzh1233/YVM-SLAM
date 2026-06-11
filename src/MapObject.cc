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

#include "MapObject.h"

namespace ORB_SLAM3
{

std::atomic<unsigned long> MapObject::nNextId{0};

MapObject::MapObject(const std::string &label, int classId, const cv::Point3f &posWorld)
    : mnId(nNextId.fetch_add(1, std::memory_order_relaxed)),
      mLabel(label),
      mClassId(classId),
      mPosWorld(posWorld),
      mSize(0.5f, 0.5f, 0.5f),
      mConfidence(0.0f),
      mObsCount(0),
      mVLMRequested(false)
{
}

long unsigned int MapObject::Id() const
{
    return mnId;
}

std::string MapObject::GetLabel() const
{
    return mLabel;
}

int MapObject::GetClassId() const
{
    return mClassId;
}

cv::Point3f MapObject::GetPosWorld() const
{
    std::unique_lock<std::mutex> lock(mMutex);
    return mPosWorld;
}

void MapObject::SetPosWorld(const cv::Point3f &posWorld)
{
    std::unique_lock<std::mutex> lock(mMutex);
    mPosWorld = posWorld;
}

cv::Point3f MapObject::GetSize() const
{
    std::unique_lock<std::mutex> lock(mMutex);
    return mSize;
}

void MapObject::SetSize(const cv::Point3f &size)
{
    std::unique_lock<std::mutex> lock(mMutex);
    mSize = size;
}

float MapObject::GetConfidence() const
{
    std::unique_lock<std::mutex> lock(mMutex);
    return mConfidence;
}

void MapObject::SetConfidence(float conf)
{
    std::unique_lock<std::mutex> lock(mMutex);
    mConfidence = conf;
}

int MapObject::GetObservationCount() const
{
    std::unique_lock<std::mutex> lock(mMutex);
    return mObsCount;
}

void MapObject::IncrementObservationCount()
{
    std::unique_lock<std::mutex> lock(mMutex);
    ++mObsCount;
}

bool MapObject::IsVLMRequested() const
{
    std::unique_lock<std::mutex> lock(mMutex);
    return mVLMRequested;
}

void MapObject::SetVLMRequested(bool requested)
{
    std::unique_lock<std::mutex> lock(mMutex);
    mVLMRequested = requested;
}

cv::Rect2i MapObject::GetLastBBox() const
{
    std::unique_lock<std::mutex> lock(mMutex);
    return mLastBBox;
}

void MapObject::SetLastBBox(const cv::Rect2i &bbox)
{
    std::unique_lock<std::mutex> lock(mMutex);
    mLastBBox = bbox;
}

void MapObject::AddObservation(const cv::Point3f &posWorld)
{
    std::unique_lock<std::mutex> lock(mMutex);
    if (mRawObservations.size() >= mMaxObsWindow)
        mRawObservations.pop_front();
    mRawObservations.push_back(posWorld);
    ++mObsCount;

    const float alpha = 0.1f;
    mPosWorld.x = mPosWorld.x * (1.0f - alpha) + posWorld.x * alpha;
    mPosWorld.y = mPosWorld.y * (1.0f - alpha) + posWorld.y * alpha;
    mPosWorld.z = mPosWorld.z * (1.0f - alpha) + posWorld.z * alpha;
}

std::vector<cv::Point3f> MapObject::GetObservations() const
{
    std::unique_lock<std::mutex> lock(mMutex);
    return std::vector<cv::Point3f>(mRawObservations.begin(), mRawObservations.end());
}

} // namespace ORB_SLAM3
