/*
* This file is part of YVM-SLAM
* Author: Balveer Singh
* GitHub: https://github.com/balveersinghyt/YVM-SLAM
*/
#ifndef YOLO_DETECT_H
#define YOLO_DETECT_H

#include <opencv2/opencv.hpp>
#include <algorithm>
#include <iostream>
#include <map>
#include <mutex>
#include <utility>
#include <vector>
#include <time.h>
using namespace std;

class YoloDetection
{
public:
    YoloDetection();
    ~YoloDetection();
    void GetImage(cv::Mat& RGB);
    void ClearImage();
    bool Detect();
    void ClearArea();
    void SetExternalMask(const cv::Mat& mask);
    void SetExternalDetections(const map<string, vector<cv::Rect2i>>& detections);
    vector<cv::Rect2i> mvPersonArea = {};

public:
    cv::Mat mRGB;
    std::vector<std::string> mClassnames;

    // 6-28
    vector<string> mvDynamicNames;
    
    vector<cv::Rect2i> mvDynamicArea;
    vector<cv:: Mat> mvDynamicMask;

    // map for detection and mask together
    map<string, vector<cv::Rect2i>> mmDetectMap;
    cv::Mat mask;
    cv::Mat objectMask;

private:
    std::mutex mMutex;
    cv::Mat mExternalMask;
    map<string, vector<cv::Rect2i>> mExternalDetections;
};


#endif //YOLO_DETECT_H
