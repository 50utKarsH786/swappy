Swappy – A Secure Campus Buy & Sell Marketplace

Swappy is a college-exclusive online marketplace built using Flask and SQLAlchemy, designed to help students buy and sell products safely within their own college community.
The platform enforces trust and transparency through college email verification, structured commission handling, product reviews, and data-driven analytics.

Project Overview

Swappy enables students to list, search, and purchase items such as books, stationery, and non-stationery products within their campus.
Access is restricted to users from the same college, ensuring a safe, localized, and scam-free trading environment.
Each transaction is recorded with automatic commission calculation, seller wallet updates, and payment tracking, making Swappy suitable for real-world campus deployment.

Authentication & Security
1.College-email-only registration (.edu / .ac.in2.)
2.Secure password hashing using Werkzeug
3.Session-based authentication
4.Role-based access control (User & Admin)

College-Specific Marketplace
1.Users can only view and purchase products from their own college
2.Automatic college detection using email domain
3.Supports multiple colleges

Product Management

1.List products with:
2.Title, description, category, brand & condition
3.Original price & selling price
4.Multiple product images with primary image selection
5.Product view count tracking
6.Admin-controlled featured products

Smart Pricing & Commission System

1.Category-based commission calculation
2.Suggested price estimation based on:
3.Product condition
4.Brand tier
5.Automatic seller wallet balance update after sale

Payments & Transactions

1.Razorpay payment gateway integration (test mode)
2.Detailed transaction records:
3.Buyer & seller details
4.Commission amount
5.Seller payout
6.Order status tracking (pending / completed / failed)

Reviews & Ratings
1.Buyers can rate and review purchased products
2.Seller profile shows average ratings
3.One review per user per product
4.Search & Analytics
5.Search activity logging
6.College-wise analytics dashboard:
7.Top searched items
8.Most listed categories
9.Category-wise demand (view counts)
10.Helps identify student demand trends

 Admin Dashboard

1.Total users, products & completed transactions
2.Total commission earned
3.Recent transaction monitoring
4.Feature / unfeature products

TECH STACK

1.Backend: Flask (Python)
2.Database: SQLite + SQLAlchemy ORM
3.Authentication: Werkzeug Security
4.File Storage: Secure image uploads
5.Payments: Razorpay (Test Integration)
6.Analytics: SQLAlchemy Aggregations
7.Migration: Flask-Migrate


