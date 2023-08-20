/*
 *  Copyright 2022 Collate.
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *  http://www.apache.org/licenses/LICENSE-2.0
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import { Typography } from 'antd';
import classNames from 'classnames';
import { capitalize, toString } from 'lodash';
import React, { Fragment, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { EntityHistory } from '../../generated/type/entityHistory';
import { getSummary, isMajorVersion } from '../../utils/EntityVersionUtils';

type Props = {
  versionList: EntityHistory;
  currentVersion: string;
  show?: boolean;
  versionHandler: (v: string) => void;
  onBack: () => void;
};
type VersionType = 'all' | 'major' | 'minor';

const EntityVersionTimeLine: React.FC<Props> = ({
  versionList = {} as EntityHistory,
  currentVersion,
  show = false,
  versionHandler,
  onBack,
}: Props) => {
  const { t } = useTranslation();
  const [versionType] = useState<VersionType>('all');
  const getVersionList = () => {
    let versionTypeList = [];
    const list = versionList.versions ?? [];

    switch (versionType) {
      case 'major':
        versionTypeList = list.filter((v) => {
          const currV = JSON.parse(v);

          return isMajorVersion(
            parseFloat(currV?.changeDescription?.previousVersion)
              .toFixed(1)
              .toString(),
            parseFloat(currV?.version).toFixed(1).toString()
          );
        });

        break;
      case 'minor':
        versionTypeList = list.filter((v) => {
          const currV = JSON.parse(v);

          return !isMajorVersion(
            parseFloat(currV?.changeDescription?.previousVersion)
              .toFixed(1)
              .toString(),
            parseFloat(currV?.version).toFixed(1).toString()
          );
        });

        break;
      case 'all':
      default:
        versionTypeList = list;

        break;
    }

    return versionTypeList.length ? (
      versionTypeList.map((v, i) => {
        const currV = JSON.parse(v);
        const majorVersionChecks = () => {
          return (
            isMajorVersion(
              parseFloat(currV?.changeDescription?.previousVersion)
                .toFixed(1)
                .toString(),
              parseFloat(currV?.version).toFixed(1).toString()
            ) && versionType === 'all'
          );
        };
        const versionText = `v${parseFloat(currV?.version).toFixed(1)}`;

        return (
          <Fragment key={currV.version}>
            {i === 0 ? (
              <div className="timeline-content tw-cursor-pointer tw--mb-2.5">
                <div className="timeline-wrapper">
                  <span className="timeline-line-se" />
                </div>
              </div>
            ) : null}
            <div
              className="timeline-content p-y-xs cursor-pointer"
              onClick={() => versionHandler(toString(currV?.version))}>
              <div className="timeline-wrapper">
                <span
                  className={classNames(
                    'timeline-rounder',
                    {
                      selected: toString(currV?.version) === currentVersion,
                    },
                    {
                      major: majorVersionChecks(),
                    }
                  )}
                  data-testid={`version-selector-${versionText}`}
                />
                <span className={classNames('timeline-line')} />
              </div>
              <div className="tw-grid tw-gap-0.5">
                <Typography.Text
                  className={classNames(' font-medium', {
                    'text-primary': toString(currV?.version) === currentVersion,
                  })}>
                  <span>{versionText}</span>
                  {majorVersionChecks() ? (
                    <span className="tw-ml-2 text-xs font-medium tw-text-grey-body tw-bg-tag tw-px-2 tw-py-0.5 tw-rounded">
                      {t('label.major')}
                    </span>
                  ) : null}
                </Typography.Text>
                <div
                  className={classNames(
                    'tw-text-xs tw-font-normal tw-break-all',
                    {
                      'diff-description':
                        toString(currV?.version) === currentVersion,
                    }
                  )}>
                  {getSummary(currV?.changeDescription)}
                </div>
                <p className="tw-text-xs tw-italic">
                  <span className="tw-font-medium">{currV?.updatedBy}</span>
                  <span className="text-grey-muted">
                    {' '}
                    {t('label.updated-on')}{' '}
                  </span>
                  <span className="tw-font-medium">
                    {new Date(currV?.updatedAt).toLocaleDateString('en-CA', {
                      hour: 'numeric',
                      minute: 'numeric',
                    })}
                  </span>
                </p>
              </div>
            </div>
          </Fragment>
        );
      })
    ) : (
      <p className="text-grey-muted d-flex tw-justify-center tw-items-center tw-mt-10">
        {t('message.no-version-type-available', {
          type: capitalize(versionType),
        })}
      </p>
    );
  };

  return (
    <div className={classNames('timeline-drawer', { open: show })}>
      <header className="d-flex tw-justify-between">
        <p className="tw-font-medium tw-mr-2">
          {t('label.version-plural-history')}
        </p>
        <div className="d-flex" onClick={onBack}>
          <svg
            className="tw-w-5 tw-h-5 tw-ml-1 tw-cursor-pointer"
            data-testid="closeDrawer"
            fill="none"
            stroke="#6B7280"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg">
            <path
              d="M6 18L18 6M6 6l12 12"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
            />
          </svg>
        </div>
      </header>
      <hr className="tw-mt-3" />

      <div className="tw-my-2 tw-pb-9">{getVersionList()}</div>
    </div>
  );
};

export default EntityVersionTimeLine;
