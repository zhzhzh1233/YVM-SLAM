/*
* This file is part of YVM-SLAM
* Author: Balveer Singh
* GitHub: https://github.com/balveersinghyt/YVM-SLAM
*/
#include <iostream>
#include <opencv2/core.hpp> // For cv::Scalar
#include <opencv2/opencv.hpp>
#include <time.h>

#include <YoloDetect.h>

YoloDetection::YoloDetection()
{
    std::cout << "YOLO-World mask mode enabled. Waiting for ROS mask." << std::endl;

    mvDynamicNames = {"person", "car", "motorbike", "bus", "train", "truck", "boat", "bird", "cat",
                      "dog", "horse", "sheep", "crow", "bear"};
}

YoloDetection::~YoloDetection()
{

}

bool YoloDetection::Detect()
{
    cv::Mat external_mask;
    map<string, vector<cv::Rect2i>> external_detections;
    {
        std::lock_guard<std::mutex> lock(mMutex);
        if (mExternalMask.empty() && mExternalDetections.empty())
            return false;
        if (!mExternalMask.empty())
            external_mask = mExternalMask.clone();
        external_detections = mExternalDetections;
        mExternalMask.release();
        mExternalDetections.clear();
    }

    mvDynamicMask.clear();
    mvDynamicArea.clear();
    mmDetectMap.clear();
    mask.release();
    objectMask.release();

    if (!external_mask.empty())
    {
        cv::Mat mask_gray;
        if (external_mask.channels() == 1)
            mask_gray = external_mask;
        else if (external_mask.channels() == 3)
            cv::cvtColor(external_mask, mask_gray, cv::COLOR_BGR2GRAY);
        else if (external_mask.channels() == 4)
            cv::cvtColor(external_mask, mask_gray, cv::COLOR_BGRA2GRAY);
        else
            mask_gray = external_mask;

        if (mask_gray.type() != CV_8UC1)
            mask_gray.convertTo(mask_gray, CV_8UC1);

        cv::threshold(mask_gray, mask_gray, 0, 255, cv::THRESH_BINARY);
        mask = mask_gray;
        objectMask = mask_gray.clone();
        mvDynamicMask.push_back(mask_gray);
    }

    if (!external_detections.empty())
    {
        mmDetectMap = external_detections;
        if (mvDynamicMask.empty())
        {
            for (const auto& entry : external_detections)
            {
                for (const auto& bbox : entry.second)
                    mvDynamicArea.push_back(bbox);
            }
        }
    }

    return !mvDynamicMask.empty() || !mmDetectMap.empty();
}


void YoloDetection::GetImage(cv::Mat &RGB)
{
    mRGB = RGB;
}

void YoloDetection::ClearImage()
{
    mRGB.release();
}

void YoloDetection::ClearArea()
{
    mvPersonArea.clear();
}

void YoloDetection::SetExternalMask(const cv::Mat& mask)
{
    std::lock_guard<std::mutex> lock(mMutex);
    if (mask.empty())
        mExternalMask.release();
    else
        mExternalMask = mask.clone();
}

void YoloDetection::SetExternalDetections(const map<string, vector<cv::Rect2i>>& detections)
{
    std::lock_guard<std::mutex> lock(mMutex);
    mExternalDetections = detections;
}
